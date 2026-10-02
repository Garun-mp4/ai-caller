from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, Request, WebSocket
from twilio.request_validator import RequestValidator

from app.core.config import get_settings


def _public_request_url(path: str, query: str = "", *, websocket: bool = False) -> str:
    settings = get_settings()
    base = urlsplit(settings.public_base_url)
    if base.scheme not in {"http", "https"} or not base.netloc:
        raise HTTPException(status_code=503, detail="Twilio public URL is not configured")
    public_path = f"{base.path.rstrip('/')}/{path.lstrip('/')}"
    scheme = base.scheme
    if websocket:
        scheme = "wss" if scheme == "https" else "ws"
    return urlunsplit((scheme, base.netloc, public_path, query, ""))


def _url_with_trailing_slash(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path if parts.path.endswith("/") else f"{parts.path}/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _settings_or_http_error() -> str:
    settings = get_settings()
    if settings.telephony_provider.casefold() != "twilio":
        raise HTTPException(status_code=404, detail="Twilio telephony is disabled")
    if not settings.twilio_auth_token:
        raise HTTPException(status_code=503, detail="Twilio webhook validation is not configured")
    return settings.twilio_auth_token


async def validate_twilio_request(request: Request) -> None:
    """Validate Twilio's signature against the configured public URL and form body."""
    token = _settings_or_http_error()
    signature = request.headers.get("x-twilio-signature", "")
    url = _public_request_url(request.url.path, request.url.query)
    form = await request.form()
    if not signature or not RequestValidator(token).validate(url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio request signature")


def validate_twilio_websocket(websocket: WebSocket) -> bool:
    """Check a Media Streams signature without trusting the proxy's internal host."""
    settings = get_settings()
    if settings.telephony_provider.casefold() != "twilio" or not settings.twilio_auth_token:
        return False

    signature = websocket.headers.get("x-twilio-signature", "")
    if not signature:
        return False

    url = _public_request_url(websocket.url.path, websocket.url.query, websocket=True)
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, {}, signature) or validator.validate(_url_with_trailing_slash(url), {}, signature)
