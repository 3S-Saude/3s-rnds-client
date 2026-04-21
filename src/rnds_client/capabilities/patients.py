from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from httpx import HTTPError, HTTPStatusError, Response

from rnds_client.base_client import RndsBaseClient
from rnds_client.exceptions import RndsAuthenticationError
from rnds_client.parsers import format_patient_payload
from rnds_client.settings import AuthMethod
from rnds_client.tokens import AccessToken, DjangoTokenCache


class PatientsCapability:
    def __init__(self, client: RndsBaseClient) -> None:
        self._client = client

    async def buscar_pessoa(self, identificador: str) -> dict[str, Any] | None:
        query_parameter = self._query_parameter(identificador)
        if query_parameter is None:
            return None

        response = await self._client.request_with_retry(
            "GET",
            self._person_url(query_parameter),
            non_retryable_statuses={400, 404},
        )
        if response is None:
            return None

        return format_patient_payload(response.json())

    async def buscar_pessoa_debug(
        self,
        identificador: str,
        *,
        force_refresh_token: bool = True,
    ) -> dict[str, Any] | None:
        attempts = 5
        non_retryable_statuses = {400, 404}
        query_parameter = self._query_parameter(identificador)
        person_url = self._person_url(query_parameter) if query_parameter is not None else None

        self._debug_print("===== buscar_pessoa_debug =====")
        self._debug_print(f"[config] identificador_informado={identificador!r}")
        self._debug_print(f"[config] identificador_normalizado={self._normalized_identifier(identificador)!r}")
        self._debug_print(f"[config] query_parameter={query_parameter!r}")
        self._debug_print(f"[config] person_url={person_url!r}")
        self._debug_print(f"[config] force_refresh_token={force_refresh_token}")
        self._debug_print(f"[config] attempts={attempts}")
        self._debug_print(f"[config] non_retryable_statuses={sorted(non_retryable_statuses)}")
        self._debug_print_configuration()

        if query_parameter is None or person_url is None:
            self._debug_print("[config] identificador invalido: informe CPF com 11 digitos ou CNS com mais de 11.")
            return None

        self._debug_print_cached_token_snapshot()

        last_error: HTTPError | None = None

        for attempt in range(attempts):
            self._debug_print(f"[request] tentativa={attempt + 1}/{attempts}")

            try:
                headers = await self._debug_headers(
                    force_refresh=force_refresh_token if attempt == 0 else False
                )
                response = await self._debug_http_request("GET", person_url, headers=headers)

                if response.status_code == 401:
                    self._debug_print(
                        "[request] status=401 recebido; renovando token e repetindo a chamada imediatamente."
                    )
                    headers = await self._debug_headers(force_refresh=True)
                    response = await self._debug_http_request("GET", person_url, headers=headers)

                response.raise_for_status()
                payload = response.json()
                formatted_payload = format_patient_payload(payload) if isinstance(payload, dict) else None
                self._debug_print(
                    f"[request] payload_formatado={self._serialize_for_log(formatted_payload)}"
                )
                return formatted_payload
            except HTTPStatusError as error:
                last_error = error
                self._debug_print(
                    f"[request] HTTPStatusError status={error.response.status_code} "
                    f"body={self._response_body_preview(error.response)}"
                )
                if error.response.status_code in non_retryable_statuses:
                    self._debug_print(
                        f"[request] status={error.response.status_code} nao reprocessavel; retornando None."
                    )
                    return None
            except HTTPError as error:
                last_error = error
                self._debug_print(f"[request] HTTPError={error!r}")

            if attempt < attempts - 1:
                sleep_time = max((2**attempt) / 10, 1.2)
                self._debug_print(
                    f"[request] aguardando {sleep_time:.1f}s antes da proxima tentativa."
                )
                await asyncio.sleep(sleep_time)

        if last_error is not None:
            raise last_error
        return None

    def _person_url(self, query_parameter: str) -> str:
        return self._client.build_service_url(
            f"fhir/r4/Patient?identifier=http://rnds.saude.gov.br/fhir/r4/NamingSystem/{query_parameter}"
        )

    @staticmethod
    def _query_parameter(identificador: str) -> str | None:
        identificador_limpo = PatientsCapability._normalized_identifier(identificador)
        if len(identificador_limpo) == 11:
            return f"cpf%7C{identificador_limpo}"
        if len(identificador_limpo) > 11:
            return f"cns%7C{identificador_limpo}"
        return None

    @staticmethod
    def _normalized_identifier(identificador: str) -> str:
        return identificador.replace(".", "").replace("-", "")

    def _debug_print_configuration(self) -> None:
        settings = self._client._settings
        last_response = self._client.response()

        self._debug_print(f"[config] RNDS_AUTH_METHOD={settings.auth_method.value}")
        self._debug_print(f"[config] RNDS_API_URL={settings.service_url!r}")
        self._debug_print(f"[config] RNDS_AUTH_TOKEN_URL={settings.auth_token_url!r}")
        self._debug_print(f"[config] RNDS_AUTH_LOGIN_URL={settings.auth_login_url!r}")
        self._debug_print(
            f"[config] RNDS_CNS_GESTOR={self._mask_secret(settings.cns_authorization)}"
        )
        self._debug_print(
            f"[config] http_client_class={type(self._client._http_client).__name__}"
        )
        self._debug_print(
            f"[config] access_token_memoria={self._mask_secret(self._client.access_token())}"
        )
        self._debug_print(
            f"[config] ultima_response_status={last_response.status_code if last_response is not None else None}"
        )

        if settings.api_credentials is not None:
            self._debug_print(f"[config] RNDS_USER={settings.api_credentials.username!r}")
            self._debug_print(
                f"[config] RNDS_PASSWORD={self._mask_secret(settings.api_credentials.password)}"
            )
        else:
            self._debug_print("[config] RNDS_USER=None")
            self._debug_print("[config] RNDS_PASSWORD=None")

        if settings.certificate_files is not None:
            certificate = settings.certificate_files.certificate
            key = settings.certificate_files.key
            self._debug_print(
                f"[config] RNDS_CERT={certificate!r} exists={os.path.exists(certificate)}"
            )
            self._debug_print(f"[config] RNDS_KEY={key!r} exists={os.path.exists(key)}")
        else:
            self._debug_print("[config] RNDS_CERT=None")
            self._debug_print("[config] RNDS_KEY=None")

    def _debug_print_cached_token_snapshot(self) -> None:
        self._debug_print(f"[cache] chave={DjangoTokenCache.key!r}")
        try:
            cached_token = DjangoTokenCache().load()
        except Exception as error:
            self._debug_print(f"[cache] erro_ao_carregar={error!r}")
            return

        if cached_token is None:
            self._debug_print("[cache] token_cache=None")
            return

        self._debug_print(f"[cache] token_cache={self._mask_secret(cached_token.value)}")
        self._debug_print(
            f"[cache] token_cache_timeout={self._token_timeout_for_log(cached_token)}"
        )

    async def _debug_headers(self, *, force_refresh: bool) -> dict[str, str]:
        self._debug_print(f"[auth] montando_headers force_refresh={force_refresh}")
        access_token = await self._debug_ensure_access_token(force_refresh=force_refresh)
        headers = {
            "Content-Type": "application/json",
            "X-Authorization-Server": f"Bearer {access_token.value}",
        }
        if self._client._settings.cns_authorization:
            headers["Authorization"] = self._client._settings.cns_authorization

        self._debug_print(
            f"[auth] headers={self._serialize_for_log(self._sanitize_headers(headers))}"
        )
        return headers

    async def _debug_ensure_access_token(self, *, force_refresh: bool) -> AccessToken:
        self._debug_print(
            f"[auth] access_token_memoria_atual={self._mask_secret(self._client.access_token())}"
        )

        if not force_refresh:
            self._debug_print(
                f"[auth] consultando_cache chave={DjangoTokenCache.key!r} para reproduzir o fluxo padrao."
            )
            cached_access_token = DjangoTokenCache().load()
            if cached_access_token is not None:
                self._client._access_token = cached_access_token
                self._debug_print(
                    f"[auth] token_carregado_do_cache={self._mask_secret(cached_access_token.value)}"
                )
                self._debug_print(
                    f"[auth] token_cache_timeout={self._token_timeout_for_log(cached_access_token)}"
                )
                return cached_access_token

            self._debug_print("[auth] cache_vazio; iniciando autenticacao remota.")
        else:
            self._debug_print("[auth] force_refresh=True; ignorando cache e autenticando novamente.")

        response = await self._debug_authenticate()
        access_token = self._access_token_from_response(response, "RNDS authentication response")
        self._debug_print(f"[auth] access_token={self._mask_secret(access_token.value)}")
        self._debug_print(f"[auth] token_cache_timeout={self._token_timeout_for_log(access_token)}")
        self._debug_print(f"[auth] salvando_token_no_cache chave={DjangoTokenCache.key!r}")
        DjangoTokenCache().save(access_token)
        self._debug_print("[auth] token_salvo_no_cache=True")

        self._client._response = response
        self._client._access_token = access_token
        return access_token

    async def _debug_authenticate(self) -> Response:
        settings = self._client._settings

        if settings.auth_method is AuthMethod.CERT:
            self._debug_print(f"[auth] metodo=CERT token_url={settings.auth_token_url!r}")
            response = await self._debug_http_request("GET", settings.auth_token_url)
            response.raise_for_status()
            return response

        self._debug_print(
            f"[auth] metodo=API login_url={settings.auth_login_url!r} token_url={settings.auth_token_url!r}"
        )
        credentials = settings.api_credentials
        login_payload = credentials.as_payload() if credentials is not None else {}
        self._debug_print(
            f"[auth] login_payload={self._serialize_for_log(self._sanitize_payload(login_payload))}"
        )
        login_response = await self._debug_http_request(
            "POST",
            settings.auth_login_url or "",
            json=login_payload,
        )
        login_response.raise_for_status()

        access_token = self._login_access_token(login_response, "RNDS API login response")
        self._debug_print(f"[auth] login_access_token={self._mask_secret(access_token)}")

        token_headers = {"Authorization": f"Bearer {access_token}"}
        self._debug_print(
            f"[auth] token_headers={self._serialize_for_log(self._sanitize_headers(token_headers))}"
        )
        token_response = await self._debug_http_request(
            "POST",
            settings.auth_token_url,
            headers=token_headers,
        )
        token_response.raise_for_status()
        return token_response

    async def _debug_http_request(self, method: str, url: str, **kwargs: Any) -> Response:
        sanitized_kwargs = self._sanitize_request_kwargs(kwargs)
        self._debug_print(f"[http] method={method} url={url!r}")
        if sanitized_kwargs:
            self._debug_print(
                f"[http] kwargs={self._serialize_for_log(sanitized_kwargs)}"
            )

        response = await self._client._http_client.request(method, url, **kwargs)
        self._debug_print(f"[http] status={response.status_code}")
        self._debug_print(
            f"[http] response_headers={self._serialize_for_log(dict(response.headers))}"
        )
        self._debug_print(f"[http] response_body={self._response_body_preview(response)}")
        return response

    @staticmethod
    def _access_token_from_response(response: Response, source: str) -> AccessToken:
        try:
            return AccessToken.from_response(response)
        except RndsAuthenticationError as error:
            raise RndsAuthenticationError(f"{source}: {error}") from error

    @staticmethod
    def _login_access_token(response: Response, source: str) -> str:
        payload = response.json()
        if not isinstance(payload, dict):
            raise RndsAuthenticationError(f"{source} must be a JSON object.")

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RndsAuthenticationError(f"{source} must contain access_token.")

        return access_token.removeprefix("Bearer ").strip()

    def _sanitize_request_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        sanitized_kwargs: dict[str, Any] = {}

        for key, value in kwargs.items():
            if key == "headers" and isinstance(value, dict):
                sanitized_kwargs[key] = self._sanitize_headers(value)
                continue

            if key == "json" and isinstance(value, dict):
                sanitized_kwargs[key] = self._sanitize_payload(value)
                continue

            sanitized_kwargs[key] = value

        return sanitized_kwargs

    def _sanitize_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        sanitized_headers: dict[str, Any] = {}

        for key, value in headers.items():
            if isinstance(value, str) and key.lower() in {"authorization", "x-authorization-server"}:
                sanitized_headers[key] = self._mask_secret(value)
                continue
            sanitized_headers[key] = value

        return sanitized_headers

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized_payload: dict[str, Any] = {}

        for key, value in payload.items():
            if isinstance(value, str) and "password" in key.lower():
                sanitized_payload[key] = self._mask_secret(value)
                continue
            sanitized_payload[key] = value

        return sanitized_payload

    @staticmethod
    def _token_timeout_for_log(access_token: AccessToken) -> str:
        try:
            return str(access_token.cache_timeout())
        except Exception as error:
            return f"erro={error!r}"

    def _response_body_preview(self, response: Response, *, limit: int = 1200) -> str:
        try:
            body = self._serialize_for_log(response.json())
        except ValueError:
            body = response.text
        return self._preview_text(body, limit=limit)

    @staticmethod
    def _serialize_for_log(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=True, default=str)

    @staticmethod
    def _preview_text(value: str, *, limit: int) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}...<truncated>"

    @staticmethod
    def _mask_secret(value: str | None, *, visible_prefix: int = 6, visible_suffix: int = 4) -> str:
        if not value:
            return "<vazio>"

        if len(value) <= visible_prefix + visible_suffix:
            return "*" * len(value)

        return f"{value[:visible_prefix]}...{value[-visible_suffix:]} (len={len(value)})"

    @staticmethod
    def _debug_print(message: str) -> None:
        print(f"[RNDS DEBUG] {message}", flush=True)
