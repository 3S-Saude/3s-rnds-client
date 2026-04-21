from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from rnds_client.exceptions import RndsConfigurationError


class AuthMethod(Enum):
    CERT = "CERT"
    API = "API"

    @classmethod
    def from_environment(cls) -> "AuthMethod":
        configured_method = os.getenv("RNDS_AUTH_METHOD")
        if configured_method:
            return cls.from_value(configured_method)

        if os.getenv("RNDS_USER") or os.getenv("RNDS_PASSWORD"):
            return cls.API

        return cls.CERT

    @classmethod
    def from_value(cls, value: str) -> "AuthMethod":
        try:
            return cls(value.upper())
        except ValueError as error:
            message = f"Unsupported RNDS_AUTH_METHOD '{value}'. Use CERT or API."
            raise RndsConfigurationError(message) from error


@dataclass(frozen=True)
class CertificateFiles:
    certificate: str
    key: str

    def as_httpx_cert(self) -> tuple[str, str]:
        return self.certificate, self.key


@dataclass(frozen=True)
class ApiCredentials:
    username: str
    password: str

    def as_payload(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password}


@dataclass(frozen=True)
class RndsSettings:
    auth_method: AuthMethod
    auth_token_url: str
    service_url: str
    auth_login_url: str | None = None
    cns_authorization: str = ""
    certificate_files: CertificateFiles | None = None
    api_credentials: ApiCredentials | None = None

    @classmethod
    def from_environment(cls) -> "RndsSettings":
        auth_method = AuthMethod.from_environment()
        service_url = _required_environment_variable("RNDS_API_URL")
        cns_authorization = _optional_environment_variable("RNDS_CNS_GESTOR", "CNS_SEC_SAUDE")
        auth_token_url = _required_environment_variable("RNDS_AUTH_TOKEN_URL")

        if auth_method is AuthMethod.CERT:
            return cls(
                auth_method=auth_method,
                auth_token_url=auth_token_url,
                service_url=service_url,
                cns_authorization=cns_authorization,
                certificate_files=CertificateFiles(
                    certificate=_required_environment_variable("RNDS_CERT"),
                    key=_required_environment_variable("RNDS_KEY"),
                ),
            )

        return cls(
            auth_method=auth_method,
            auth_token_url=auth_token_url,
            service_url=service_url,
            auth_login_url=_required_environment_variable("RNDS_AUTH_LOGIN_URL"),
            cns_authorization=cns_authorization,
            api_credentials=ApiCredentials(
                username=_required_environment_variable("RNDS_USER"),
                password=_required_environment_variable("RNDS_PASSWORD"),
            ),
        )


def _required_environment_variable(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RndsConfigurationError(f"Environment variable '{name}' is required.")


def _optional_environment_variable(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""
