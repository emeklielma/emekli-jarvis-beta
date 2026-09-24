from tools.registry import register_tool
from core import telephony


@register_tool(
    name="call_my_phone",
    description=(
        "Calls the user's OWN phone (Linphone internet call, or a normal call via Twilio) so they can talk to Jarvis. "
        "It can only ever call the owner's configured number. Use when the user says 'beni ara', "
        "'telefonumu ara' or 'call me'."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "reason": {"type": "STRING", "description": "Optional short sentence Jarvis says when the user answers."}
        }
    }
)
def call_my_phone(reason: str = "") -> str:
    return telephony.call_owner_any(reason)
