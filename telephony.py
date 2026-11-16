"""Twilio telephony provider and the TwiML conversation flow.

Implements the TelephonyProvider protocol from integrations.py using
Twilio's REST API over httpx (no Twilio SDK). Outbound calls point Twilio
at this app's /v1/calls/voice webhook; inbound calls handed to
handle_inbound get the same flow. The flow greets the caller as Aptivo,
gathers speech, answers with agent.answer() (the Groq-backed brain, wired
in main.py), and loops until the caller says goodbye or stops answering.
"""
from xml.sax.saxutils import escape

import httpx

from .config import settings

XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>'
GATHER_ACTION = "/v1/calls/gather"


def twilio_configured() -> bool:
    """True only when every Twilio setting is non-empty."""
    return all([
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_phone_number,
        settings.public_base_url,
    ])


def _say(text: str) -> str:
    return f"<Say>{escape(text)}</Say>"


def _gather(action: str, prompt: str) -> str:
    return (
        f'<Gather input="speech" action="{escape(action, {chr(34): "&quot;"})}"'
        f' method="POST" speechTimeout="auto">{_say(prompt)}</Gather>'
    )


def _response(*verbs: str) -> str:
    return XML_DECL + "<Response>" + "".join(verbs) + "</Response>"


def greeting_twiml() -> str:
    """Opening TwiML: greet as Aptivo and gather the caller's request."""
    return _response(
        _say("Hello, this is Aptivo, your assistant."),
        _gather(GATHER_ACTION, "How can I help you today?"),
        _say("I didn't hear anything. Goodbye."),
        "<Hangup/>",
    )


def reply_twiml(reply: str) -> str:
    """Speak the agent's reply, then gather again for a follow-up."""
    return _response(
        _say(reply),
        _gather(GATHER_ACTION, "Is there anything else I can help with?"),
        _say("Thanks for calling. Goodbye."),
        "<Hangup/>",
    )


def reprompt_twiml() -> str:
    """One reprompt after empty speech; the next gather carries retry=1."""
    return _response(
        _say("Sorry, I didn't catch that."),
        _gather(GATHER_ACTION + "?retry=1", "Please tell me what you need."),
        _say("Thanks for calling. Goodbye."),
        "<Hangup/>",
    )


def closing_twiml() -> str:
    """Closing line and hang up."""
    return _response(
        _say("Thanks for calling. Goodbye."),
        "<Hangup/>",
    )


class TwilioProvider:
    """TelephonyProvider backed by Twilio Programmable Voice."""

    async def place_call(self, to_number: str, purpose: str) -> dict:
        sid = settings.twilio_account_sid
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
        data = {
            "From": settings.twilio_phone_number,
            "To": to_number,
            "Url": f"{settings.public_base_url.rstrip('/')}/v1/calls/voice",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url, data=data, auth=(sid, settings.twilio_auth_token)
                )
        except (httpx.HTTPError, httpx.InvalidURL) as e:
            raise RuntimeError(
                f"Twilio could not place the call: {e}"
            ) from e
        if response.status_code >= 400:
            message = response.text
            try:
                message = response.json().get("message") or message
            except ValueError:
                pass
            raise RuntimeError(
                f"Twilio could not place the call "
                f"(HTTP {response.status_code}): {message}"
            )
        body = response.json()
        return {
            "sid": body.get("sid"),
            "status": body.get("status"),
            "to": body.get("to"),
            "from": body.get("from"),
            "purpose": purpose,
        }

    async def handle_inbound(self, payload: dict) -> dict:
        return {"accepted": True, "provider": "twilio", "twiml": greeting_twiml()}
