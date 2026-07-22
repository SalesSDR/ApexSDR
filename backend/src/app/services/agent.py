import json
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai
from pydantic import BaseModel
import os
from .ai import generate_outreach_message # Fallback

logger = logging.getLogger(__name__)

# Configure API key
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "dummy"))

# Define schemas for structured output
class ReplyIntent(BaseModel):
    intent: str
    confidence: float
    suggested_action: str

# Define Tools
def search_prospect_context(prospect_id: str) -> str:
    """Fetches enriched CRM and web context for a given prospect ID."""
    # Mock implementation for orchestration demo
    logger.info(f"Tool Call: search_prospect_context({prospect_id})")
    return json.dumps({
        "prospect_id": prospect_id,
        "name": "Jane Smith",
        "company": "TechNova",
        "recent_funding": "$10M Series A",
        "technologies": ["Next.js", "Python", "AWS"]
    })

def draft_channel_outreach(channel: str, tone: str, context: str = "") -> str:
    """Drafts highly personalized outreach for a specific channel (e.g., email, linkedin) matching the given tone."""
    logger.info(f"Tool Call: draft_channel_outreach(channel={channel}, tone={tone})")
    if channel.lower() == "linkedin":
        return f"Hey, noticed TechNova's recent Series A! Given your stack, ApexSDR could streamline your GTM. Open to connecting?"
    return f"Hi Jane,\n\nCongratulations on the recent $10M Series A for TechNova! I noticed you are using Next.js and Python. I'd love to show you how ApexSDR integrates seamlessly.\n\nBest,\nSales"

def classify_reply_intent(incoming_text: str) -> str:
    """Classifies the intent of an incoming reply from a prospect."""
    logger.info(f"Tool Call: classify_reply_intent(incoming_text={incoming_text[:20]}...)")
    text_lower = incoming_text.lower()
    if "meeting" in text_lower or "chat" in text_lower or "call" in text_lower:
        return json.dumps({"intent": "MEETING_REQUESTED"})
    elif "not interested" in text_lower or "unsubscribe" in text_lower:
        return json.dumps({"intent": "REFUSAL"})
    elif "?" in text_lower or "how much" in text_lower:
        return json.dumps({"intent": "QUESTION"})
    elif "out of office" in text_lower or "ooo" in text_lower:
        return json.dumps({"intent": "OUT_OF_OFFICE"})
    return json.dumps({"intent": "UNKNOWN"})


class GeminiOrchestrator:
    def __init__(self, model_name="gemini-1.5-pro"):
        self.model_name = model_name
        self.tools = [search_prospect_context, draft_channel_outreach, classify_reply_intent]
        try:
            self.model = genai.GenerativeModel(model_name=self.model_name, tools=self.tools)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None

    async def run_agent_loop(self, prompt: str) -> str:
        """Runs the agent with tool calling orchestration."""
        if not self.model:
            logger.warning("Gemini model not initialized. Using fallback.")
            return await generate_outreach_message("Prospect", "Company", "linkedin", True)

        try:
            logger.info("Starting Gemini agent tool-calling loop...")
            chat = self.model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API Error or Timeout: {e}. Falling back to ai.py basic generator.")
            # Fallback to ai.py basic generator
            return await generate_outreach_message("Prospect", "Company", "linkedin", True)
            
    async def draft_channel_outreach(self, channel: str, tone: str, context: str) -> str:
        """Helper to invoke the agent specifically for drafting outreach."""
        prompt = f"Using the following context: {context}, draft a {tone} {channel} outreach message."
        return await self.run_agent_loop(prompt)

    async def classify_intent(self, text: str) -> Dict[str, Any]:
        """Helper to classify intent utilizing structured output or tool."""
        prompt = f"Classify the intent of this reply: '{text}'. Use the classify_reply_intent tool and return the exact JSON."
        res = await self.run_agent_loop(prompt)
        try:
            # Attempt to parse what the model returned as JSON
            return json.loads(res)
        except json.JSONDecodeError:
            # Fallback if the model returned conversational text
            return {"intent": "UNKNOWN", "raw": res}

# Singleton instance
agent_orchestrator = GeminiOrchestrator()
