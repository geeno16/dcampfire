import os
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

_SECRET_KEY = os.getenv("SECRET_KEY")
if not _SECRET_KEY:
    raise RuntimeError("Environment variable SECRET_KEY is not set")

_ALGORITHM = os.getenv("ALGORITHM", "HS256")
_TOKEN_TTL = timedelta(
    minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + _TOKEN_TTL,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token, _SECRET_KEY, algorithms=[_ALGORITHM]
        )
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
