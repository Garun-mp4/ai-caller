import asyncio
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode
import httpx
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException
from app.core.config import get_settings

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
JWKS = ISSUER + "/.well-known/jwks.json"
_transactions: dict[str, dict] = {}

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def begin_chatgpt_login() -> str:
    s = get_settings()
    if not s.openai_oauth_client_id:
        raise HTTPException(503, "Sign in with ChatGPT is not configured. Set OPENAI_OAUTH_CLIENT_ID or use AUTH_MODE=local.")
    state = secrets.token_urlsafe(32); nonce = secrets.token_urlsafe(32); verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    _transactions[state] = {"nonce": nonce, "verifier": verifier, "created": time.time()}
    # Drop expired one-time transactions.
    for k, v in list(_transactions.items()):
        if time.time() - v["created"] > 600:
            _transactions.pop(k, None)
    params = {
        "response_type": "code", "client_id": s.openai_oauth_client_id,
        "redirect_uri": s.openai_oauth_redirect_uri, "scope": "openid profile email",
        "state": state, "nonce": nonce, "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return AUTHORIZE + "?" + urlencode(params)

async def finish_chatgpt_login(code: str, state: str) -> dict:
    s = get_settings(); tx = _transactions.pop(state, None)
    if not tx or time.time() - tx["created"] > 600:
        raise HTTPException(400, "Invalid or expired OAuth state")
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": s.openai_oauth_redirect_uri, "client_id": s.openai_oauth_client_id, "code_verifier": tx["verifier"]}
    headers = {"accept": "application/json", "content-type": "application/x-www-form-urlencoded"}
    auth = httpx.BasicAuth(s.openai_oauth_client_id, s.openai_oauth_client_secret) if s.openai_oauth_client_secret else None
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(TOKEN, data=data, headers=headers, auth=auth)
    if r.status_code >= 400:
        raise HTTPException(400, "OpenAI OAuth token exchange failed")
    token_data = r.json(); id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(400, "OpenAI OAuth response did not include an ID token")
    def verify():
        key = PyJWKClient(JWKS).get_signing_key_from_jwt(id_token).key
        return jwt.decode(id_token, key, algorithms=["RS256", "ES256"], audience=s.openai_oauth_client_id, issuer=ISSUER)
    try:
        claims = await asyncio.to_thread(verify)
    except Exception as e:
        raise HTTPException(400, "Could not validate OpenAI ID token") from e
    if claims.get("nonce") != tx["nonce"]:
        raise HTTPException(400, "OAuth nonce mismatch")
    return {"sub": str(claims.get("sub", "")), "email": claims.get("email"), "name": claims.get("name") or claims.get("preferred_username") or claims.get("email") or "ChatGPT user"}
