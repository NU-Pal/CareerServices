import base64
import json
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

# Matches NUPAL.Core resume/job controllers: User.Identity?.Name is usually email or unique_name.
_CLAIM_EMAIL = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
_CLAIM_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"


def decode_student_email_from_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization[7:].strip()
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("not a JWT")
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        email = (
            payload.get("email")
            or payload.get("unique_name")
            or payload.get(_CLAIM_EMAIL)
            or payload.get(_CLAIM_NAME)
            or payload.get("name")
            or payload.get("nameid")
            or payload.get("sub")
        )
        if not email:
            raise ValueError("no user identity in token")
        return str(email).strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not read user from token",
        ) from exc


def require_service_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> None:
    if not settings.career_services_api_key:
        return
    if x_api_key and x_api_key == settings.career_services_api_key:
        return
    if authorization and authorization.startswith("Bearer "):
        if authorization[7:].strip() == settings.career_services_api_key:
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing service API key",
    )


def get_student_email(
    authorization: str | None = Header(None),
) -> str:
    return decode_student_email_from_bearer(authorization)


# Backward-compatible name for routers
get_user_id = get_student_email
