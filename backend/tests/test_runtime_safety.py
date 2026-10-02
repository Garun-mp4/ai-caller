import pytest
from fastapi.testclient import TestClient

from app.api.routes import S
from app.core.config import Settings
from app.core.runtime_safety import validate_runtime_configuration
from app.main import app


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "local_admin_username": "operator",
        "local_admin_password": "unique-operator-password",
        "jwt_secret": "a-production-signing-secret-that-is-long-enough",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_are_allowed_outside_production():
    validate_runtime_configuration(Settings(_env_file=None, app_env="development"))


def test_application_lifespan_refuses_unsafe_production_configuration(monkeypatch):
    monkeypatch.setattr(S, "app_env", "production")

    with pytest.raises(RuntimeError, match="LOCAL_ADMIN_USERNAME"):
        with TestClient(app):
            pass


def test_production_rejects_default_credentials_without_echoing_them():
    settings = production_settings(local_admin_password="admin", jwt_secret="local-development-secret-change-me")

    with pytest.raises(RuntimeError) as error:
        validate_runtime_configuration(settings)

    message = str(error.value)
    assert "LOCAL_ADMIN_PASSWORD" in message
    assert "JWT_SECRET" in message
    assert "admin" not in message
    assert "local-development-secret-change-me" not in message


def test_production_mock_telephony_requires_safe_local_auth_but_no_twilio_secrets():
    validate_runtime_configuration(production_settings(telephony_provider="mock"))


def test_production_twilio_requires_credentials_and_public_https():
    settings = production_settings(telephony_provider="twilio", public_base_url="http://localhost:8000")

    with pytest.raises(RuntimeError) as error:
        validate_runtime_configuration(settings)

    message = str(error.value)
    assert "TWILIO_ACCOUNT_SID" in message
    assert "TWILIO_AUTH_TOKEN" in message
    assert "TWILIO_PHONE_NUMBER" in message
    assert "PUBLIC_BASE_URL" in message


def test_production_twilio_accepts_complete_configuration():
    settings = production_settings(
        telephony_provider="twilio",
        twilio_account_sid="AC" + "1" * 32,
        twilio_auth_token="twilio-token-for-test-only",
        twilio_phone_number="+12025550123",
        public_base_url="https://voice.example.test",
    )
    validate_runtime_configuration(settings)
