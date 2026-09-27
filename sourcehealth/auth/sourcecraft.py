"""User PAT connection: encrypted Redis, bound to one existing Я ID session."""

import base64
import logging
import secrets
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from sourcehealth.application.services import ServiceError
from sourcehealth.integrations.sourcecraft.analytics import identifier
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
from sourcehealth.storage.models import User

LOG = logging.getLogger(__name__)


class SourceCraftConnection:
    def __init__(self, auth, *, client_factory=SourceCraftClient):
        self.auth = auth
        self.redis = auth.redis
        self.settings = auth.settings
        self.client_factory = client_factory

    def _cipher(self):
        secret = self.settings.sourcecraft_credential_key
        if not secret:
            raise ServiceError("sourcecraft_connection_not_configured", 503)
        value = secret.get_secret_value()
        if self.settings.session_secret and value == self.settings.session_secret.get_secret_value():
            raise ServiceError("sourcecraft_connection_key_invalid", 503)
        try:
            key = base64.b64decode(value, altchars=b"-_", validate=True)
            if len(key) != 32:
                raise ValueError
            return AESGCM(key)
        except (ValueError, TypeError):
            raise ServiceError("sourcecraft_connection_key_invalid", 503) from None

    RETENTIONS = {1800, 21600, 86400, 604800}

    def _keys(self, token):
        user = self.auth.current_user(token) if token else None
        if not user:
            raise ServiceError("authentication_required", 401)
        return self.auth._key("session", token), self.auth._key("user-sourcecraft", str(user["id"])), UUID(user["id"])

    def connect(self, token, pat, retention_seconds=1800):
        if retention_seconds not in self.RETENTIONS:
            raise ServiceError("invalid_sourcecraft_retention", 422)
        session_key, key, user_id = self._keys(token)
        cipher = self._cipher()
        try:
            with self.client_factory(pat=pat, deadline_seconds=20) as client:
                identifier(client.get("/user").get("id"))
        except SourceCraftError:
            raise ServiceError("sourcecraft_credential_unverified", 400) from None
        nonce = secrets.token_bytes(12)
        encrypted = nonce + cipher.encrypt(nonce, pat.encode(), key.encode())
        # Atomic session existence/TTL check avoids reconnect racing with logout.
        ttl = self.redis.eval(
            "local t=redis.call('TTL',KEYS[1]); if t<=0 then return 0 end; "
            "local n=tonumber(ARGV[2]); redis.call('SET',KEYS[2],ARGV[1],'EX',n); return n",
            2, session_key, key, encrypted, retention_seconds)
        if not ttl:
            raise ServiceError("authentication_required", 401)
        with self.auth.sessions.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is not None:
                user.sourcecraft_retention_seconds = retention_seconds
        return {"connected": True, "expires_in": ttl, "retention_seconds": retention_seconds}

    def status(self, token):
        if not token:
            return {"connected": False, "expires_in": 0}
        _, key, user_id = self._keys(token)
        ttl = self.redis.ttl(key)
        with self.auth.sessions() as db:
            retention = db.scalar(select(User.sourcecraft_retention_seconds).where(User.id == user_id)) or 1800
        return {"connected": ttl > 0, "expires_in": max(0, ttl), "retention_seconds": retention}

    def disconnect(self, token):
        _, key, _ = self._keys(token)
        self.redis.delete(key)

    def update_retention(self, token, retention_seconds):
        if retention_seconds not in self.RETENTIONS:
            raise ServiceError("invalid_sourcecraft_retention", 422)
        _, key, user_id = self._keys(token)
        if not self._decrypt(key):
            raise ServiceError("sourcecraft_connection_required", 409)
        if not self.redis.expire(key, retention_seconds):
            raise ServiceError("sourcecraft_connection_required", 409)
        with self.auth.sessions.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is not None:
                user.sourcecraft_retention_seconds = retention_seconds
        return {"connected": True, "expires_in": retention_seconds,
                "retention_seconds": retention_seconds}

    def _decrypt(self, key):
        encrypted = self.redis.get(key)
        if not encrypted:
            return None
        try:
            return self._cipher().decrypt(encrypted[:12], encrypted[12:], key.encode()).decode()
        except (InvalidTag, ValueError, UnicodeError):
            self.redis.delete(key)
            return None

    @staticmethod
    def _analysis_key(analysis_id):
        # Analysis UUID is already unguessable and is the RQ identity; unlike a browser token it need not be HMACed.
        return f"auth:analysis-sourcecraft:{UUID(str(analysis_id))}"

    def lease_for_analysis(self, token, analysis_id):
        if not token:
            return False
        _, credential_key, _ = self._keys(token)
        pat = self._decrypt(credential_key)
        ttl = self.redis.ttl(credential_key)
        if not pat or ttl <= 0:
            return False
        run_key = self._analysis_key(analysis_id)
        nonce = secrets.token_bytes(12)
        encrypted = nonce + self._cipher().encrypt(nonce, pat.encode(), run_key.encode())
        return bool(self.redis.set(run_key, encrypted, ex=min(
            ttl, self.settings.sourcecraft_connection_ttl, self.settings.analysis_timeout + 300), nx=True))

    def lease_user_for_analysis(self, user_id, analysis_id):
        """Create a short run lease from an explicitly retained user credential."""
        credential_key = self.auth._key("user-sourcecraft", str(UUID(str(user_id))))
        pat = self._decrypt(credential_key)
        ttl = self.redis.ttl(credential_key)
        if not pat or ttl <= 0:
            return False
        run_key = self._analysis_key(analysis_id)
        nonce = secrets.token_bytes(12)
        encrypted = nonce + self._cipher().encrypt(nonce, pat.encode(), run_key.encode())
        return bool(self.redis.set(
            run_key, encrypted, ex=min(ttl, self.settings.analysis_timeout + 300), nx=True))

    def analysis_credential(self, analysis_id):
        return self._decrypt(self._analysis_key(analysis_id))

    def delete_analysis_credential(self, analysis_id):
        self.redis.delete(self._analysis_key(analysis_id))

    def repositories(self, token, organization):
        _, key, _ = self._keys(token)
        pat = self._decrypt(key)
        if not pat:
            raise ServiceError("sourcecraft_connection_required", 409)
        try:
            identifier(organization)
        except SourceCraftError:
            raise ServiceError("invalid_organization", 422) from None
        try:
            with self.client_factory(pat=pat, deadline_seconds=20, max_pages=1) as client:
                payload = client.get(f"/orgs/{organization}/repos", params={"page_size": 100})
            rows = payload.get("repositories")
            if not isinstance(rows, list):
                raise SourceCraftError("invalid_response")
            if len(rows) > 100:
                raise SourceCraftError("item_limit")
            items = []
            for row in rows:
                slug = identifier(row.get("slug"))
                visibility = row.get("visibility")
                if visibility not in {"public", "private", "internal"}:
                    raise SourceCraftError("invalid_response")
                items.append({"url": f"https://sourcecraft.dev/{organization}/{slug}",
                              "visibility": visibility, "can_analyze": visibility == "public"})
            return {"items": items, "has_more": bool(payload.get("next_page_token"))}
        except (SourceCraftError, AttributeError, TypeError):
            raise ServiceError("sourcecraft_repositories_unavailable", 503) from None

    def my_repositories(self, token, page_token=None):
        _, key, _ = self._keys(token)
        pat = self._decrypt(key)
        if not pat:
            raise ServiceError("sourcecraft_connection_required", 409)
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        try:
            with self.client_factory(pat=pat, deadline_seconds=20, max_pages=1) as client:
                payload = client.get("/me/repos", params=params)
            rows = payload.get("repositories")
            if not isinstance(rows, list) or len(rows) > 100:
                raise SourceCraftError("invalid_response")
            items = []
            for row in rows:
                repo_id, slug = identifier(row.get("id")), identifier(row.get("slug"))
                organization = row.get("organization")
                org = identifier(organization.get("slug") if isinstance(organization, dict) else None)
                visibility = row.get("visibility")
                if visibility not in {"public", "private", "internal"}:
                    raise SourceCraftError("invalid_response")
                branch = row.get("default_branch")
                if branch == "":
                    branch = None
                # Git refs may contain Unicode. Keep a bounded display value and reject
                # control characters; this field is never used to construct a URL or command.
                if branch is not None and (not isinstance(branch, str) or not 1 <= len(branch) <= 255
                                           or any(ord(char) < 32 or ord(char) == 127 for char in branch)):
                    raise SourceCraftError("invalid_response")
                is_empty = row.get("is_empty")
                if is_empty is not None and type(is_empty) is not bool:
                    raise SourceCraftError("invalid_response")
                items.append({"id": repo_id, "organization_slug": org, "repository_slug": slug,
                              "url": f"https://sourcecraft.dev/{org}/{slug}", "visibility": visibility,
                              "default_branch": branch, "is_empty": is_empty,
                              "can_analyze": visibility == "public"})
            next_token = payload.get("next_page_token")
            if next_token not in (None, "") and not isinstance(next_token, str):
                raise SourceCraftError("invalid_pagination")
            return {"items": items, "next_page_token": next_token or None, "has_more": bool(next_token)}
        except SourceCraftError as exc:
            # Only the stable integration code and logical endpoint are safe for operator logs.
            LOG.warning("sourcecraft_request_failed", extra={"endpoint": "me/repos",
                                                               "sourcecraft_error_code": exc.code})
            raise ServiceError("sourcecraft_repositories_unavailable", 503) from None
        except (AttributeError, TypeError):
            LOG.warning("sourcecraft_request_failed", extra={"endpoint": "me/repos",
                                                               "sourcecraft_error_code": "invalid_response"})
            raise ServiceError("sourcecraft_repositories_unavailable", 503) from None
