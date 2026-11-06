from __future__ import annotations

import asyncio
import logging
from typing import Any
from contextlib import nullcontext

from httpx import AsyncClient, HTTPError, HTTPStatusError, Response

from rnds_client.auth import AuthenticationFactory, build_http_client
from rnds_client.settings import RndsSettings
from rnds_client.tokens import AccessToken, DjangoTokenCache

logger = logging.getLogger(__name__)


def _request_body_len(kwargs: dict[str, Any]) -> int | None:
    content = kwargs.get("content")
    if isinstance(content, (bytes, str)):
        return len(content)
    if "json" in kwargs:
        return None
    return None


class RndsBaseClient:
    def __init__(
        self,
        settings: RndsSettings,
        http_client: AsyncClient,
        response: Response | None = None,
        access_token: AccessToken | None = None,
        *, attempts: int = 5, token_cache=None, token_lock=None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._response = response
        self._access_token = access_token
        if attempts < 1:
            raise ValueError("O número de tentativas deve ser positivo.")
        self._attempts = attempts
        self._token_cache = token_cache
        self._token_lock = token_lock or nullcontext

    @classmethod
    async def create(cls, *, http_timeout=None, attempts: int = 5, token_cache=None, token_lock=None) -> "RndsBaseClient":
        settings = RndsSettings.from_environment()
        http_client = build_http_client(settings) if http_timeout is None else build_http_client(settings, timeout=http_timeout)
        try:
            client = cls(settings=settings, http_client=http_client, attempts=attempts,
                         token_cache=token_cache, token_lock=token_lock)
            await client._ensure_access_token()
        except BaseException:
            await http_client.aclose()
            raise
        return client

    async def _load_token(self):
        if self._token_cache is not None:
            return await self._token_cache.load()
        return await asyncio.to_thread(DjangoTokenCache().load)

    async def _ensure_access_token(self, force_refresh: bool = False) -> AccessToken:
        anterior = self._access_token
        if not force_refresh:
            cached = await self._load_token()
            if cached is not None:
                self._access_token = cached
                return cached
        async with self._token_lock():
            cached = await self._load_token()
            if cached is not None and (not force_refresh or (anterior and cached.value != anterior.value)):
                self._access_token = cached
                return cached
            response = await self._authenticate(self._settings, self._http_client)
            access_token = AccessToken.from_response(response)
            if self._token_cache is not None:
                await self._token_cache.save(access_token)
            else:
                await asyncio.to_thread(DjangoTokenCache().save, access_token)
            self._response = response
            self._access_token = access_token
            return access_token

    @staticmethod
    async def _authenticate(settings: RndsSettings, http_client: AsyncClient) -> Response:
        strategy = AuthenticationFactory().create(settings)
        response = await strategy.authenticate(http_client)
        response.raise_for_status()
        return response

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def headers(self, force_refresh: bool = False) -> dict[str, str]:
        access_token = await self._ensure_access_token(force_refresh=force_refresh)
        headers = {
            "Content-Type": "application/json",
            "X-Authorization-Server": f"Bearer {access_token.value}",
        }
        if self._settings.cns_authorization:
            headers["Authorization"] = self._settings.cns_authorization
        return headers

    async def request(
        self, method: str, url: str, *, retry_on_401: bool = True, **kwargs: Any
    ) -> Response:
        user_headers = dict(kwargs.pop("headers", {}))

        request_headers = {**await self.headers(), **user_headers}
        self._log_request(method, url, request_headers, kwargs)
        response = await self._http_client.request(method, url, headers=request_headers, **kwargs)

        if response.status_code == 401 and retry_on_401:
            request_headers = {**await self.headers(force_refresh=True), **user_headers}
            self._log_request(method, url, request_headers, kwargs)
            response = await self._http_client.request(method, url, headers=request_headers, **kwargs)

        self._log_response(method, url, response)
        response.raise_for_status()
        return response

    @staticmethod
    def _log_request(method: str, url: str, headers: dict[str, str], kwargs: dict[str, Any]) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        logger.debug(
            "RNDS request %s %s (body_len=%s)",
            method, url, _request_body_len(kwargs),
        )

    @staticmethod
    def _log_response(method: str, url: str, response: Response) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        logger.debug(
            "RNDS response %s %s -> %s (location=%s)",
            method, url, response.status_code, response.headers.get("location"),
        )

    async def request_with_retry(
        self,
        method: str,
        url: str,
        *,
        attempts: int | None = None,
        non_retryable_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> Response | None:
        attempts = self._attempts if attempts is None else attempts
        last_error: HTTPError | None = None

        for attempt in range(attempts):
            try:
                return await self.request(method, url, **kwargs)
            except HTTPStatusError as error:
                last_error = error
                if non_retryable_statuses and error.response.status_code in non_retryable_statuses:
                    return None
            except HTTPError as error:
                last_error = error

            if attempt < attempts - 1:
                sleep_time = max((2**attempt) / 10, 1.2)
                await asyncio.sleep(sleep_time)

        if last_error is not None:
            raise last_error
        return None

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self.request("POST", url, **kwargs)

    def build_service_url(self, path: str) -> str:
        base_url = self._settings.service_url.rstrip("/") + "/"
        return f"{base_url}{path.lstrip('/')}"

    def response(self) -> Response | None:
        return self._response

    def access_token(self) -> str | None:
        return self._access_token.value if self._access_token is not None else None

    def payload(self) -> Any:
        return self._response.json() if self._response is not None else None
