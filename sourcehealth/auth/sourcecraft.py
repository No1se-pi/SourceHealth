"""User PAT connection: encrypted Redis, bound to one existing Я ID session."""

import base64
import secrets
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sourcehealth.application.services import ServiceError
from sourcehealth.integrations.sourcecraft.analytics import identifier
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError


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

    def _keys(self, token):
        if not token or not self.auth.current_user(token):
            raise ServiceError("authentication_required", 401)
        return self.auth._key("session", token), self.auth._key("sourcecraft", token)

    def connect(self, token, pat):
        session_key, key = self._keys(token)
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
            "local n=math.min(t,tonumber(ARGV[2])); redis.call('SET',KEYS[2],ARGV[1],'EX',n); return n",
            2, session_key, key, encrypted, self.settings.sourcecraft_connection_ttl)
        if not ttl:
            raise ServiceError("authentication_required", 401)
        return {"connected": True, "expires_in": ttl}

    def status(self, token):
        _, key = self._keys(token)
        ttl = self.redis.ttl(key)
        return {"connected": ttl > 0, "expires_in": max(0, ttl)}

    def disconnect(self, token):
        _, key = self._keys(token)
        self.redis.delete(key)

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
        _, session_key = self._keys(token)
        pat = self._decrypt(session_key)
        ttl = self.redis.ttl(session_key)
        if not pat or ttl <= 0:
            return False
        run_key = self._analysis_key(analysis_id)
        nonce = secrets.token_bytes(12)
        encrypted = nonce + self._cipher().encrypt(nonce, pat.encode(), run_key.encode())
        self.redis.set(run_key, encrypted, ex=min(ttl, self.settings.sourcecraft_connection_ttl,
                                                  self.settings.analysis_timeout + 300))
        return True

    def analysis_credential(self, analysis_id):
        return self._decrypt(self._analysis_key(analysis_id))

    def delete_analysis_credential(self, analysis_id):
        self.redis.delete(self._analysis_key(analysis_id))

    def repositories(self, token, organization):
        _, key = self._keys(token)
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
