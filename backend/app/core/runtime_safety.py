from urllib.parse import urlparse

from app.core.config import Settings


def validate_runtime_configuration(settings: Settings) -> None:
    """Fail closed when production is configured with known development defaults."""
    if settings.app_env.casefold() not in {"prod", "production"}:
        return

    problems: list[str] = []
    auth_mode = settings.auth_mode.casefold()
    if auth_mode not in {"local", "chatgpt"}:
        problems.append("AUTH_MODE must be local or chatgpt")
    if auth_mode == "local":
        if settings.local_admin_username.casefold() == "admin":
            problems.append("LOCAL_ADMIN_USERNAME must be changed from the built-in default")
        password = settings.local_admin_password
        if password.casefold() in {"admin", "password", "changeme"} or len(password) < 12:
            problems.append("LOCAL_ADMIN_PASSWORD must be a unique value of at least 12 characters")

    if settings.jwt_secret == "local-development-secret-change-me" or len(settings.jwt_secret) < 32:
        problems.append("JWT_SECRET must be a unique value of at least 32 characters")

    if auth_mode == "chatgpt" and not (
        settings.openai_oauth_client_id and settings.openai_oauth_client_secret
    ):
        problems.append("OPENAI_OAUTH_CLIENT_ID and OPENAI_OAUTH_CLIENT_SECRET are required for ChatGPT authentication")
    if auth_mode == "chatgpt" and urlparse(settings.openai_oauth_redirect_uri).scheme != "https":
        problems.append("OPENAI_OAUTH_REDIRECT_URI must use https in production")

    if settings.telephony_provider.casefold() == "twilio":
        missing = [
            name
            for name, value in (
                ("TWILIO_ACCOUNT_SID", settings.twilio_account_sid),
                ("TWILIO_AUTH_TOKEN", settings.twilio_auth_token),
                ("TWILIO_PHONE_NUMBER", settings.twilio_phone_number),
            )
            if not value
        ]
        if missing:
            problems.append(f"{', '.join(missing)} are required when TELEPHONY_PROVIDER=twilio")
        parsed = urlparse(settings.public_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            problems.append("PUBLIC_BASE_URL must be an https URL when TELEPHONY_PROVIDER=twilio")

    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
