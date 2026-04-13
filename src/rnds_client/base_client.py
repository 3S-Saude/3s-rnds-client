from __future__ import annotations

import asyncio
from typing import Any

from httpx import AsyncClient, HTTPError, HTTPStatusError, Response

from rnds_client.auth import AuthenticationFactory, build_http_client
from rnds_client.settings import RndsSettings
from rnds_client.tokens import AccessToken, DjangoTokenCache


class RndsBaseClient:
    def __init__(
        self,
        settings: RndsSettings,
        http_client: AsyncClient,
        response: Response | None = None,
        access_token: AccessToken | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._response = response
        self._access_token = access_token

    @classmethod
    async def create(cls) -> "RndsBaseClient":
        settings = RndsSettings.from_environment()
        http_client = build_http_client(settings)
        client = cls(settings=settings, http_client=http_client)

        try:
            await client._ensure_access_token()
        except Exception:
            await http_client.aclose()
            raise

        return client

    async def _ensure_access_token(self, force_refresh: bool = False) -> AccessToken:
        if not force_refresh:
            cached_access_token = DjangoTokenCache().load()
            if cached_access_token is not None:
                self._access_token = cached_access_token
                return cached_access_token

        response = await self._authenticate(self._settings, self._http_client)
        access_token = AccessToken.from_response(response)
        DjangoTokenCache().save(access_token)

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
        return {
            "Content-Type": "application/json",
            "X-Authorization-Server": f"Bearer {access_token.value}",
            "Authorization": self._settings.cns_authorization,
        }

    async def request(self, method: str, url: str, **kwargs: Any) -> Response:
        user_headers = dict(kwargs.pop("headers", {}))
        response = await self._http_client.request(
            method,
            url,
            headers={**await self.headers(), **user_headers},
            **kwargs,
        )

        if response.status_code in {401, 403}:
            response = await self._http_client.request(
                method,
                url,
                headers={**await self.headers(force_refresh=True), **user_headers},
                **kwargs,
            )

        response.raise_for_status()
        return response

    async def request_with_retry(
        self,
        method: str,
        url: str,
        *,
        attempts: int = 5,
        non_retryable_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> Response | None:
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

