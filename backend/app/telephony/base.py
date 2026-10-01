from abc import ABC, abstractmethod
class TelephonyProvider(ABC):
    @abstractmethod
    async def create_call(self, phone_number: str, call_id: int) -> dict: ...
    async def health(self) -> dict: return {"ok": True}
