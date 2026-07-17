import asyncio
import httpx
import json
import sys
import os

# Add src/ to python path so it can import app
sys.path.append(os.path.dirname(__file__))

async def test_ai_fallback():
    print("\n--- Testing AI Service Resiliency (Phase 3) ---")
    from app.services.ai import generate_outreach_message
    
    print("Requesting AI Message Generation (Simulating 429 Quota Exceeded fallback)...")
    message = await generate_outreach_message("Alice", "TechCorp", prompt_type="linkedin", fallback_mode=True)
    print("Resulting Message:", message)
    print("✅ AI fallback logic successfully executed!")

async def test_webhook():
    print("\n--- Testing Unipile Webhook Endpoint (Phase 2) ---")
    url = "http://api_gateway:8000/api/v1/webhooks/unipile"
    
    payload = {
        "event": "message:received",
        "data": {
            "sender_id": "test_provider_id_123",
            "text": "Yes, I would love to connect and chat about this!",
            "message_id": "msg_987654"
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            print("Webhook HTTP Status:", response.status_code)
            print("Webhook Response Body:", response.json())
            if response.status_code == 200:
                print("✅ Webhook endpoint successfully parsed and accepted the inbound payload!")
            else:
                print("❌ Webhook failed!")
        except Exception as e:
            print("❌ Webhook connection failed:", e)

async def main():
    print("=========================================")
    print("   AUTONOMOUS PIPELINE INTEGRATION TEST")
    print("=========================================")
    await test_webhook()
    await test_ai_fallback()
    print("\n=========================================\n")

if __name__ == "__main__":
    asyncio.run(main())
