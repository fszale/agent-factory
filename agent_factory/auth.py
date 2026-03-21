from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status

from agent_factory.persistence import PersistenceStore


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * ((4 - len(payload) % 4) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    public_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    raw_key = f"afc_{public_id}_{secret}"
    return raw_key, f"afc_{public_id}", hash_api_key(raw_key)


def encode_jwt_hs256(claims: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
            _b64url_encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_jwt_hs256(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed bearer token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    provided_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token signature")

    header = json.loads(_b64url_decode(encoded_header))
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported bearer token algorithm")

    payload = json.loads(_b64url_decode(encoded_payload))
    now = int(time.time())
    if "exp" in payload and int(payload["exp"]) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token expired")
    if "nbf" in payload and int(payload["nbf"]) > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token not active yet")
    return payload


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


@dataclass(slots=True)
class Principal:
    kind: str
    identifier: str
    scopes: set[str] = field(default_factory=set)
    allowed_twins: set[str] = field(default_factory=lambda: {"*"})
    is_admin: bool = False
    factory_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def can(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes

    def can_access_twin(self, twin_id: str) -> bool:
        return "*" in self.allowed_twins or twin_id in self.allowed_twins

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "scopes": sorted(self.scopes),
            "allowed_twins": sorted(self.allowed_twins),
            "is_admin": self.is_admin,
            "factory_id": self.factory_id,
            "metadata": self.metadata,
        }


class AuthService:
    def __init__(
        self,
        store: PersistenceStore,
        require_auth: bool | None = None,
        supabase_jwt_secret: str | None = None,
    ) -> None:
        self.store = store
        self.require_auth = require_auth if require_auth is not None else os.getenv("AGENT_FACTORY_REQUIRE_AUTH", "false").lower() == "true"
        self.supabase_jwt_secret = supabase_jwt_secret or os.getenv("SUPABASE_JWT_SECRET")

    def authenticate_request(self, request: Request) -> Principal:
        api_key = request.headers.get("x-api-key")
        authorization = request.headers.get("authorization", "")
        bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None

        if api_key:
            return self._authenticate_api_key(api_key)
        if bearer:
            if looks_like_jwt(bearer):
                return self._authenticate_admin_jwt(bearer)
            return self._authenticate_api_key(bearer)

        if self.require_auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        return Principal(
            kind="anonymous",
            identifier="anonymous",
            scopes={"*"},
            allowed_twins={"*"},
            is_admin=True,
            metadata={"mode": "development-bypass"},
        )

    def require(
        self,
        principal: Principal,
        scopes: list[str] | None = None,
        twin_id: str | None = None,
        admin_only: bool = False,
    ) -> Principal:
        if admin_only and not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        for scope in scopes or []:
            if not principal.can(scope):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing scope '{scope}'")
        if twin_id and not principal.can_access_twin(twin_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to twin '{twin_id}'")
        return principal

    def _authenticate_api_key(self, raw_key: str) -> Principal:
        parts = raw_key.split("_", 2)
        if len(parts) != 3 or parts[0] != "afc":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed API key")
        key_prefix = f"{parts[0]}_{parts[1]}"
        record = self.store.get_api_client_by_prefix(key_prefix)
        if not record or record.get("status") != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown API client")
        if not hmac.compare_digest(record["key_hash"], hash_api_key(raw_key)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        self.store.touch_api_client_usage(record["id"])
        return Principal(
            kind="api_client",
            identifier=record["client_id"],
            scopes=set(record.get("allowed_actions") or []),
            allowed_twins=set(record.get("allowed_twins") or ["*"]),
            is_admin=False,
            factory_id=record.get("factory_id"),
            metadata={"name": record.get("name"), "row_id": record.get("id")},
        )

    def _authenticate_admin_jwt(self, token: str) -> Principal:
        if not self.supabase_jwt_secret:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin JWT verification is not configured")
        claims = decode_jwt_hs256(token, self.supabase_jwt_secret)
        user_id = str(claims.get("sub") or "")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token missing subject")
        record = self.store.get_admin_identity(user_id)
        if not record or record.get("status") != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an active admin")
        scopes = set(record.get("allowed_actions") or [])
        if record.get("role") in {"admin", "superadmin"} and not scopes:
            scopes = {"*"}
        return Principal(
            kind="admin_user",
            identifier=user_id,
            scopes=scopes or {"*"},
            allowed_twins=set(record.get("allowed_twins") or ["*"]),
            is_admin=True,
            metadata={
                "email": record.get("email") or claims.get("email"),
                "role": record.get("role"),
            },
        )
