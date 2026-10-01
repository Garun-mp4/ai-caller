import json, re
from app.schemas.common import AgentDecision

ALLOWED_ACTIONS = {"continue","end_call","callback","interested","hot_lead","do_not_call"}

def parse_agent_decision(text: str) -> AgentDecision:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I|re.S)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return AgentDecision(speech=raw[:360] or "Понял.", action="continue", stage="discovery")
        data = json.loads(m.group(0))
    action = str(data.get("action", "continue")).lower()
    if action not in ALLOWED_ACTIONS:
        action = "continue"
    return AgentDecision(
        speech=str(data.get("speech") or "Понял.")[:500],
        action=action,
        stage=str(data.get("stage") or "discovery").lower(),
        callback_at=data.get("callback_at"),
        reason=data.get("reason"),
    )
