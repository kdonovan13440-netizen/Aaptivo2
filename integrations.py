"""Provider-neutral integration contracts. No external actions occur until configured."""
from typing import Protocol

class TelephonyProvider(Protocol):
    async def place_call(self, to_number: str, purpose: str) -> dict: ...
    async def handle_inbound(self, payload: dict) -> dict: ...

class CalendarProvider(Protocol):
    async def list_events(self, start: str, end: str) -> list[dict]: ...
    async def create_event(self, event: dict) -> dict: ...

class NotConfigured:
    async def place_call(self, *args, **kwargs):
        raise RuntimeError("Telephony provider is not configured.")
    async def handle_inbound(self, payload):
        return {"accepted": False, "reason": "No telephony provider configured."}
    async def list_events(self, *args, **kwargs):
        raise RuntimeError("Calendar OAuth/provider is not configured.")
    async def create_event(self, *args, **kwargs):
        raise RuntimeError("Calendar OAuth/provider is not configured.")
