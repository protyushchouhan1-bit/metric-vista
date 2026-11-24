"""
Phase 1 Hardened Auth, Multi-Tenant Token Verification & Read-Only Demo Mode.
- Zero forged-header trust (X-Org-Id / X-Role bypass REMOVED).
- Uses PyJWT when installed (with strict HS256 fallback for minimal environments).
- Fails loudly at startup if NEXUS_JWT_SECRET is missing or left as a default in production.
- Demo mode is strictly READ-ONLY ('demo-org-public', role='viewer').
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

try:
    import jwt  # type: ignore
    HAS_PYJWT = True
except ImportError:
    HAS_PYJWT = False

INSECURE_DEFAULTS = {"", "changeme", "secret", "nexus-dev-jwt-secret-rotate-in-prod"}


def _load_jwt_secret() -> str:
    secret = os.getenv("NEXUS_JWT_SECRET", "").strip()
    env_mode = os.getenv("NEXUS_ENV", "development").strip().lower()
    if secret in INSECURE_DEFAULTS:
        if env_mode in {"production", "prod", "staging"}:
            raise RuntimeError(
                "FATAL SECURITY ERROR: NEXUS_JWT_SECRET must be set to a strong secret in production."
            )
        # In local/test mode, generate an ephemeral per-process secret rather than a hardcoded string
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")
        os.environ["NEXUS_JWT_SECRET"] = secret
    return secret


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
DEMO_ORG_ID = "demo-org-public"

ROLE_PERMISSIONS = {
    "platform_admin": {"platform:health"},
    "org_admin": {
        "org:settings", "dataset:upload", "mapping:confirm", "dashboard:view",
        "ai:ask", "export:data", "audit:read", "dataset:delete",
    },
    "dept_manager": {
        "dataset:upload", "mapping:confirm", "dashboard:view", "ai:ask", "export:data", "audit:read",
    },
    "analyst": {
        "dataset:upload", "mapping:confirm", "dashboard:view", "ai:ask", "export:data",
    },
    "viewer": {
        "dashboard:view", "ai:ask",
    },
}


@dataclass
class TenantContext:
    user_id: str
    organization_id: str
    role: str
    email: str = "viewer@nexus.local"
    is_demo: bool = False

    def require(self, permission: str) -> None:
        perms = ROLE_PERMISSIONS.get(self.role, set())
        if permission not in perms:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{self.role}' is not permitted to perform '{permission}'.",
            )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user_id: str, organization_id: str, role: str = "org_admin", email: str = "user@nexus.local") -> str:
    payload = {
        "sub": user_id,
        "org_id": organization_id,
        "role": role,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    if HAS_PYJWT:
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{body}".encode("utf-8")
    sig = _b64url_encode(hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def verify_token(token: str) -> TenantContext:
    if HAS_PYJWT:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc
    else:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Malformed bearer token.")
        header_b64, body_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{body_b64}".encode("utf-8")
        expected_sig = _b64url_encode(hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b64, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid token signature.")
        try:
            payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Corrupted token payload.") from exc
        if int(payload.get("exp", 0)) < int(time.time()):
            raise HTTPException(status_code=401, detail="Session token expired.")

    if "org_id" not in payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token missing required tenant claims.")

    return TenantContext(
        user_id=str(payload["sub"]),
        organization_id=str(payload["org_id"]),
        role=str(payload.get("role", "viewer")),
        email=str(payload.get("email", "user@nexus.local")),
        is_demo=False,
    )


def get_tenant_context(
    authorization: Optional[str] = Header(default=None),
    x_demo_mode: Optional[str] = Header(default=None),
) -> TenantContext:
    """
    Strictly verifies Bearer JWT token and extracts org_id + role ONLY from verified claims.
    Forged headers (X-Org-Id, X-Role) are completely ignored -> returns 401.
    Demo Mode (X-Demo-Mode: true) is strictly read-only ('demo-org-public', role='viewer').
    """
    if authorization and authorization.lower().startswith("bearer "):
        return verify_token(authorization.split(" ", 1)[1].strip())

    if x_demo_mode and x_demo_mode.lower() == "true":
        return TenantContext(
            user_id="demo-viewer",
            organization_id=DEMO_ORG_ID,
            role="viewer",
            email="demo@projectnexus.local",
            is_demo=True,
        )

    raise HTTPException(status_code=401, detail="Authentication required. Provide a valid Bearer JWT token.")
