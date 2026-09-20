"""Authorization Code + PKCE и серверные Redis-сессии с opaque cookies."""

import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from sourcehealth.application.services import ServiceError
from sourcehealth.storage.models import User


class AuthService:
    def __init__(self, settings, redis, sessions, *, transport=None) -> None:
        self.settings, self.redis, self.sessions = settings, redis, sessions
        self.transport = transport

    def _configured(self) -> None:
        settings = self.settings
        if not (settings.yandex_client_id and settings.yandex_client_secret and settings.session_secret
                and len(settings.session_secret.get_secret_value()) >= 32):
            raise ServiceError("auth_not_configured", 503)
        origin = urlsplit(settings.public_origin)
        callback = urlsplit(settings.yandex_redirect_uri)
        if (origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"}
                or origin.query or origin.fragment or origin.username
                or callback.scheme != origin.scheme or callback.netloc != origin.netloc
                or callback.path != "/api/v1/auth/yandex/callback" or callback.query or callback.fragment):
            raise ServiceError("auth_configuration_invalid", 503)
        if origin.scheme != "https" and (settings.cookie_secure or origin.hostname not in {"localhost", "127.0.0.1"}):
            raise ServiceError("auth_configuration_invalid", 503)

    def _key(self, kind: str, token: str) -> str:
        self._configured()
        digest = hmac.new(self.settings.session_secret.get_secret_value().encode(), token.encode(), hashlib.sha256)
        return f"auth:{kind}:{digest.hexdigest()}"

    def login(self) -> tuple[str, str]:
        self._configured()
        state, verifier, browser_token = (secrets.token_urlsafe(32) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.redis.set(self._key("pending", browser_token), json.dumps({"state": state, "verifier": verifier}), ex=600)
        query = urlencode({"response_type": "code", "client_id": self.settings.yandex_client_id,
                           "redirect_uri": self.settings.yandex_redirect_uri, "state": state,
                           "code_challenge": challenge, "code_challenge_method": "S256"})
        return f"https://oauth.yandex.ru/authorize?{query}", browser_token

    def callback(self, *, browser_token: str, state: str, code: str) -> str:
        self._configured()
        # GETDEL atomically consumes the browser-bound state, preventing replay.
        pending = self.redis.getdel(self._key("pending", browser_token))
        if not pending:
            raise ServiceError("invalid_oauth_state", 400)
        data = json.loads(pending)
        if not hmac.compare_digest(data["state"], state):
            raise ServiceError("invalid_oauth_state", 400)
        try:
            with httpx.Client(timeout=15, follow_redirects=False, transport=self.transport) as client:
                response = client.post("https://oauth.yandex.ru/token", data={
                    "grant_type": "authorization_code", "code": code, "code_verifier": data["verifier"],
                    "client_id": self.settings.yandex_client_id,
                    "client_secret": self.settings.yandex_client_secret.get_secret_value(),
                    "redirect_uri": self.settings.yandex_redirect_uri,
                })
                if response.status_code != 200:
                    raise ValueError("token_exchange_failed")
                token = response.json()["access_token"]
                response = client.get("https://login.yandex.ru/info", params={"format": "json"},
                                      headers={"Authorization": f"OAuth {token}"})
                if response.status_code != 200:
                    raise ValueError("identity_request_failed")
                yandex_id = response.json()["id"]
                if not isinstance(yandex_id, str) or not yandex_id or len(yandex_id) > 128:
                    raise ValueError("invalid_identity")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ServiceError("oauth_exchange_failed", 502) from None
        with self.sessions.begin() as db:
            db.execute(insert(User).values(id=uuid4(), yandex_id=yandex_id).on_conflict_do_nothing())
            user = db.scalar(select(User).where(User.yandex_id == yandex_id))
            user_id = str(user.id)
        session_token = secrets.token_urlsafe(32)
        self.redis.set(self._key("session", session_token), json.dumps({"id": user_id}), ex=self.settings.session_ttl)
        # OAuth token deliberately not retained: it cannot authorize SourceCraft PAT calls.
        return session_token

    def current_user(self, token: str | None) -> dict | None:
        if not token:
            return None
        raw = self.redis.get(self._key("session", token))
        return json.loads(raw) if raw else None

    def logout(self, token: str | None) -> None:
        if token:
            self.redis.delete(self._key("session", token), self._key("sourcecraft", token))
