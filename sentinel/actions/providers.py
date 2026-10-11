"""Message providers. This demo has exactly ONE working provider, SimulatedProvider: it records a message
as sent and delivered on the simulated clock and never contacts any network. The others are disabled stubs
so a pilot can see where a real gateway would plug in; they raise NotImplementedError. A test fails if the
demo settings name any provider other than `simulated`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class MessageProvider(ABC):
    name = "abstract"

    @abstractmethod
    def send(self, message: dict, today: date, fail: bool) -> dict:
        """Returns {'status': ..., 'sent_at': ..., 'delivered_at': ...}."""


class SimulatedProvider(MessageProvider):
    """Never sends anything. Marks the message sent and (unless the simulated network fails) delivered."""
    name = "simulated"

    def send(self, message: dict, today: date, fail: bool) -> dict:
        if fail:
            return {"status": "failed_simulated", "sent_at": today, "delivered_at": None}
        return {"status": "delivered_simulated", "sent_at": today, "delivered_at": today}


class _Disabled(MessageProvider):
    def send(self, message: dict, today: date, fail: bool) -> dict:
        raise NotImplementedError(f"{self.name} is a disabled stub: this demo never sends real messages")


class AfricasTalkingProvider(_Disabled):
    name = "africastalking"


class TwilioProvider(_Disabled):
    name = "twilio"


class SmtpProvider(_Disabled):
    name = "smtp"


PROVIDERS = {p.name: p for p in (SimulatedProvider, AfricasTalkingProvider, TwilioProvider, SmtpProvider)}


def get_provider(name: str) -> MessageProvider:
    if name != "simulated":
        raise RuntimeError(f"messaging.provider is {name!r}; this demo only allows 'simulated'")
    return SimulatedProvider()
