from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import get_settings

bearer = HTTPBearer(auto_error=False)

def create_token(username: str) -> str:
    s = get_settings()
    payload = {"sub": username, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")

def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    s = get_settings()
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, s.jwt_secret, algorithms=["HS256"])
        return str(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
