import asyncio
from .base import TelephonyProvider
class MockTelephonyProvider(TelephonyProvider):
    async def create_call(self, phone_number: str, call_id: int) -> dict:
        await asyncio.sleep(0.05)
        return {"sid": f"MOCK-{call_id}", "status": "queued"}
