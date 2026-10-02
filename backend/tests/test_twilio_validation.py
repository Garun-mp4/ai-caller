from datetime import datetime, timezone

from fastapi.testclient import TestClient
from starlette.websockets import WebSocket
from twilio.request_validator import RequestValidator

from app.api import routes
from app.api.routes import S
from app.db.session import get_db
from app.main import app
from app.models import Call, Lead
from app.telephony.request_validation import validate_twilio_websocket


def _public_url(path: str, query: str = "", *, websocket: bool = False) -> str:
    url = f"{S.public_base_url.rstrip('/')}{path}"
    if websocket:
        url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    return url + (f"?{query}" if query else "")


def _signature(path: str, params: dict[str, str] | None = None, query: str = "", *, websocket: bool = False) -> str:
    return RequestValidator(S.twilio_auth_token).compute_signature(
        _public_url(path, query, websocket=websocket), params or {}
    )


def _enable_twilio(monkeypatch, token="test-twilio-token"):
    monkeypatch.setattr(S, "telephony_provider", "twilio")
    monkeypatch.setattr(S, "twilio_auth_token", token)


def test_twilio_endpoints_are_disabled_in_mock_mode():
    with TestClient(app) as client:
        response = client.post("/api/telephony/twiml/1")
    assert response.status_code == 404


def test_twilio_webhook_rejects_missing_or_invalid_signature(monkeypatch):
    _enable_twilio(monkeypatch)
    with TestClient(app) as client:
        missing = client.post("/api/telephony/twiml/1")
        invalid = client.post(
            "/api/telephony/twiml/1",
            headers={"X-Twilio-Signature": "invalid"},
        )
    assert missing.status_code == 403
    assert invalid.status_code == 403


def test_twilio_webhook_returns_configuration_error_without_auth_token(monkeypatch):
    _enable_twilio(monkeypatch, token="")
    with TestClient(app) as client:
        response = client.post("/api/telephony/twiml/1")
    assert response.status_code == 503


def test_valid_signed_twiml_request_uses_the_configured_public_url(monkeypatch):
    _enable_twilio(monkeypatch)
    path = "/api/telephony/twiml/42"
    query = "source=voice"
    signature = _signature(path, query=query)

    with TestClient(app) as client:
        response = client.post(
            path + "?" + query,
            headers={"X-Twilio-Signature": signature},
        )

    assert response.status_code == 200
    assert "<Stream url='ws://localhost:8000/api/telephony/media/42'" in response.text


def test_valid_signed_status_callback_updates_call(db, monkeypatch):
    _enable_twilio(monkeypatch)
    lead = Lead(phone="+12025550123", status="NEW")
    db.add(lead)
    db.flush()
    call = Call(lead_id=lead.id, phone=lead.phone, status="RINGING", started_at=datetime.now(timezone.utc))
    db.add(call)
    db.commit()

    path = f"/api/telephony/status/{call.id}"
    form = {"CallStatus": "completed", "CallSid": "CA-test"}
    signature = _signature(path, form)
    with TestClient(app) as client:
        response = client.post(
            path,
            data=form,
            headers={"X-Twilio-Signature": signature},
        )

    assert response.status_code == 204
    db.refresh(call)
    db.refresh(lead)
    assert call.twilio_call_sid == "CA-test"
    assert call.status == "COMPLETED"
    assert lead.status == "DONE"


def test_media_stream_signature_includes_public_url_and_query(monkeypatch):
    _enable_twilio(monkeypatch)
    path = "/api/telephony/media/12"
    query = "track=inbound"
    headers = [(b"x-twilio-signature", _signature(path, query=query, websocket=True).encode())]
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "scheme": "ws",
        "server": ("internal-service", 8000),
        "client": ("127.0.0.1", 12345),
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": headers,
        "subprotocols": [],
    }
    socket = WebSocket(scope, receive=lambda: None, send=lambda _: None)

    assert validate_twilio_websocket(socket) is True

    trailing_slash_signature = RequestValidator(S.twilio_auth_token).compute_signature(
        _public_url(path + "/", query, websocket=True), {}
    )
    slash_scope = {**scope, "headers": [(b"x-twilio-signature", trailing_slash_signature.encode())]}
    assert validate_twilio_websocket(WebSocket(slash_scope, receive=lambda: None, send=lambda _: None)) is True

    bad_scope = {**scope, "headers": [(b"x-twilio-signature", b"invalid")]}
    assert validate_twilio_websocket(WebSocket(bad_scope, receive=lambda: None, send=lambda _: None)) is False


def test_readiness_checks_database_while_liveness_stays_available():
    class BrokenDatabase:
        def execute(self, statement):
            from sqlalchemy.exc import OperationalError

            raise OperationalError(str(statement), {}, Exception("database offline"))

    def broken_db():
        yield BrokenDatabase()

    app.dependency_overrides[get_db] = broken_db
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            response = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not ready"
