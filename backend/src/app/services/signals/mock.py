import random

from app.models.schemas import Prospect, SignalStrength, SignalType
from app.services.signals.base import BaseSignalProvider


class MockSignalProvider(BaseSignalProvider):
    async def fetch_signals(self, prospect: Prospect) -> list[dict]:
        """
        Generates deterministic, realistic mock signals based on random probability.
        """
        signals = []
        
        # 10% chance to generate a random signal
        if random.random() < 0.1:
            signal_choice = random.choice([
                {
                    "signal_type": SignalType.JOB_CHANGE,
                    "signal_source": "MOCK_LINKEDIN",
                    "signal_strength": SignalStrength.VERY_HIGH,
                    "confidence": 0.95,
                    "summary": f"{prospect.first_name} recently changed jobs.",
                },
                {
                    "signal_type": SignalType.COMPANY_HIRING,
                    "signal_source": "MOCK_NEWS",
                    "signal_strength": SignalStrength.MEDIUM,
                    "confidence": 0.8,
                    "summary": f"{prospect.company_name or 'The company'} is hiring for sales roles.",
                },
                {
                    "signal_type": SignalType.WEBSITE_VISIT,
                    "signal_source": "MOCK_TRACKER",
                    "signal_strength": SignalStrength.LOW,
                    "confidence": 1.0,
                    "summary": f"{prospect.email} visited the pricing page.",
                }
            ])
            signals.append(signal_choice)
            
        return signals
