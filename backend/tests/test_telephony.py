import pytest
from app.telephony.mock_provider import MockTelephonyProvider
@pytest.mark.asyncio
async def test_mock_telephony():
    r=await MockTelephonyProvider().create_call("+79991111111",12); assert r["sid"]=="MOCK-12"
