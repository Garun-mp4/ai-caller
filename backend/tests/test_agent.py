import pytest
from app.agent.parser import parse_agent_decision
from app.llm.mock_provider import MockLLMProvider

def test_structured_output_parser():
    d=parse_agent_decision('{"speech":"ok","action":"hot_lead","stage":"next_step"}')
    assert d.action=="hot_lead" and d.speech=="ok"

@pytest.mark.asyncio
async def test_mock_llm_do_not_call():
    raw=await MockLLMProvider().generate("",[],"Больше мне не звоните")
    assert parse_agent_decision(raw).action=="do_not_call"
