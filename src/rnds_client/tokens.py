from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

from httpx import Response

from rnds_client.exceptions import RndsAuthenticationError, RndsConfigurationError


@dataclass(frozen=True)
class AccessToken:
    value: str

    @classmethod
    def from_cached_value(cls, value: str) -> "AccessToken":
        return cls(value=value)

    @classmethod
    def from_response(cls, response: Response) -> "AccessToken":
        payload = response.json()
        if not isinstance(payload, dict):
            raise RndsAuthenticationError("RNDS authentication response must be a JSON object.")

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RndsAuthenticationError("RNDS authentication response must contain access_token.")

        return cls(value=access_token)

    def cache_timeout(self) -> int:
        expiration = self._expiration_timestamp()
        timeout = int(expiration - time.time())
        if timeout <= 0:
            raise RndsAuthenticationError("RNDS access token has already expired.")
        return timeout

    def _expiration_timestamp(self) -> int:
        payload = self._jwt_payload()
        expiration = payload.get("exp")
        if not isinstance(expiration, (int, float)):
            raise RndsAuthenticationError("RNDS access token must contain a numeric exp claim.")
        return int(expiration)

    def _jwt_payload(self) -> dict[str, Any]:
        parts = self.value.split(".")
        if len(parts) != 3:
            raise RndsAuthenticationError("RNDS access token is not a valid JWT.")

        encoded_payload = parts[1]
        padding = "=" * (-len(encoded_payload) % 4)

        try:
            decoded_payload = base64.urlsafe_b64decode(encoded_payload + padding)
            payload = json.loads(decoded_payload)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RndsAuthenticationError("Unable to decode RNDS access token payload.") from error

        if not isinstance(payload, dict):
            raise RndsAuthenticationError("RNDS access token payload must be a JSON object.")
        return payload


class DjangoTokenCache:
    key = "token_rnds"

    def load(self) -> AccessToken | None:
        cached_token = _django_cache().get(self.key)
        if not cached_token:
            return None
        return AccessToken.from_cached_value(cached_token)

    def save(self, access_token: AccessToken) -> None:
        timeout = access_token.cache_timeout()
        cache = _django_cache()
        cache.set(self.key, access_token.value, timeout=timeout)


def _django_cache() -> Any:
    try:
        from django.core.cache import cache
    except ModuleNotFoundError as error:
        raise RndsConfigurationError("Django must be installed to cache the RNDS access token.") from error
    return cache

