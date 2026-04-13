from __future__ import annotations

from dataclasses import dataclass

from httpx import AsyncClient, Response

from rnds_client.exceptions import RndsAuthenticationError, RndsConfigurationError
from rnds_client.settings import ApiCredentials, AuthMethod, RndsSettings


class AuthenticationStrategy:
    async def authenticate(self, client: AsyncClient) -> Response:
        raise NotImplementedError


@dataclass(frozen=True)
class CertificateAuthentication(AuthenticationStrategy):
    url: str

    async def authenticate(self, client: AsyncClient) -> Response:
        return await client.get(self.url)


@dataclass(frozen=True)
class ApiAuthentication(AuthenticationStrategy):
    login_url: str
    token_url: str
    credentials: ApiCredentials

    async def authenticate(self, client: AsyncClient) -> Response:
        login_response = await client.post(self.login_url, json=self.credentials.as_payload())
        login_response.raise_for_status()

        access_token = _access_token_from_response(login_response, "RNDS API login response")
        token_response = await client.post(
            self.token_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_response.raise_for_status()
        return token_response


class AuthenticationFactory:
    def create(self, settings: RndsSettings) -> AuthenticationStrategy:
        if settings.auth_method is AuthMethod.CERT:
            return self._certificate_authentication(settings)
        return self._api_authentication(settings)

    @staticmethod
    def _certificate_authentication(settings: RndsSettings) -> CertificateAuthentication:
        if settings.certificate_files is None:
            raise RndsConfigurationError("CERT authentication requires RNDS_CERT and RNDS_KEY.")
        return CertificateAuthentication(url=settings.auth_token_url)

    @staticmethod
    def _api_authentication(settings: RndsSettings) -> ApiAuthentication:
        if settings.api_credentials is None or settings.auth_login_url is None:
            raise RndsConfigurationError(
                "API authentication requires RNDS_USER, RNDS_PASSWORD and RNDS_AUTH_LOGIN_URL."
            )
        return ApiAuthentication(
            login_url=settings.auth_login_url,
            token_url=settings.auth_token_url,
            credentials=settings.api_credentials,
        )


def build_http_client(settings: RndsSettings) -> AsyncClient:
    if settings.auth_method is AuthMethod.CERT:
        if settings.certificate_files is None:
            raise RndsConfigurationError("CERT authentication requires RNDS_CERT and RNDS_KEY.")
        return AsyncClient(cert=settings.certificate_files.as_httpx_cert(), verify=True)
    return AsyncClient()


def _access_token_from_response(response: Response, source: str) -> str:
    payload = response.json()
    if not isinstance(payload, dict):
        raise RndsAuthenticationError(f"{source} must be a JSON object.")

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RndsAuthenticationError(f"{source} must contain access_token.")

    return access_token.removeprefix("Bearer ").strip()

