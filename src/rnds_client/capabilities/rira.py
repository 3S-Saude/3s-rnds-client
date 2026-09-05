from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from httpx import HTTPError, HTTPStatusError, Response

from rnds_client.base_client import RndsBaseClient
from rnds_client.rira.exceptions import ResultadoRiraIncerto
from rnds_client.rira.results import ResultadoEnvioRira
from rnds_client.rira.schemas.rira_document import RiraDocumentData
from rnds_client.rira.services import sender
from rnds_client.rira.settings import RiraFhirSettings

_BUNDLE_PATH = "fhir/r4/Bundle"

_COMPOSITION_STATUS = {
    "pending": "pending",
    "booked": "booked",
    "attended": "attended",
    "returned-to-requester": "returned-to-requester",
}


class RiraCapability:
    def __init__(self, client: RndsBaseClient) -> None:
        self._client = client

    async def enviar_rira(
        self,
        dados: RiraDocumentData,
        identificador_local: str,
        *,
        status_rira: str,
        identifier_system: str | None = None,
        predecessor_composition_id: str | None = None,
    ) -> ResultadoEnvioRira:
        composition_status = _COMPOSITION_STATUS.get(status_rira)
        if composition_status is None:
            raise ValueError(f"status_rira inválido: {status_rira!r}")

        dados = _com_id_local(dados, identificador_local)

        try:
            settings = RiraFhirSettings.from_environment()
            if identifier_system:
                settings = _com_identifier_system(settings, identifier_system)
            bundle_dict = sender.montar_bundle(
                dados, settings, composition_status, predecessor_composition_id
            )
            await self._client.headers()
        except Exception as exc:
            raise sender.classificar_erro_http(exc, apos_post=False) from exc

        url = self._client.build_service_url(_BUNDLE_PATH)
        content = json.dumps(bundle_dict, ensure_ascii=False).encode()
        response = await self._postar_bundle(url, content)

        location = response.headers.get("location", "")
        bundle_id, composition_id = sender.extrair_ids_resposta(response)

        if not bundle_id and location:
            bundle_id = sender.extrair_id_rnds(location)

        if not location and not bundle_id:
            raise ResultadoRiraIncerto(
                "POST aceito mas sem Location nem corpo utilizável.", codigo="resposta_perdida"
            )

        if not composition_id and bundle_id:
            try:
                composition_id = await self._composition_id_por_get(bundle_id)
            except HTTPError:
                composition_id = None

        return ResultadoEnvioRira(
            http_status=response.status_code,
            location_rnds=location or None,
            id_rnds_bundle=bundle_id,
            id_rnds_composition=composition_id,
        )

    async def consultar_rira(
        self, identifier_system: str, identifier_value: str
    ) -> list[ResultadoEnvioRira]:
        url = self._client.build_service_url("identifier")
        params = {"system": identifier_system, "value": identifier_value, "docType": "RA"}
        response = await self._client.request_with_retry(
            "GET", url, params=params, non_retryable_statuses={404}
        )
        if response is None or not response.text:
            return []
        corpo = response.json()

        if isinstance(corpo, dict) and corpo.get("resourceType") == "Bundle":
            itens = [e.get("resource") for e in corpo.get("entry", []) or [] if isinstance(e, dict)]
        elif isinstance(corpo, list):
            itens = corpo
        else:
            itens = [corpo]

        resultados: list[ResultadoEnvioRira] = []
        for item in itens:
            if not isinstance(item, dict):
                continue
            bundle_id, composition_id = _ids_do_documento_consulta(item)
            location = item.get("location") or item.get("url")
            if not bundle_id and location:
                bundle_id = location.rstrip("/").split("/")[-1]
            if not bundle_id:
                continue
            resultados.append(
                ResultadoEnvioRira(
                    http_status=response.status_code,
                    location_rnds=location,
                    id_rnds_bundle=bundle_id,
                    id_rnds_composition=composition_id,
                )
            )
        return resultados

    async def _postar_bundle(self, url: str, content: bytes) -> Response:
        try:
            return await self._client.request("POST", url, content=content, retry_on_401=False)
        except HTTPStatusError as exc:
            if exc.response.status_code != 401:
                raise sender.classificar_erro_http(exc, apos_post=True) from exc
        except HTTPError as exc:
            raise sender.classificar_erro_http(exc, apos_post=True) from exc

        try:
            await self._client.headers(force_refresh=True)
        except HTTPError as exc:
            raise sender.classificar_erro_http(exc, apos_post=False) from exc

        try:
            return await self._client.request("POST", url, content=content, retry_on_401=False)
        except HTTPError as exc:
            raise sender.classificar_erro_http(exc, apos_post=True) from exc

    async def _composition_id_por_get(self, bundle_id: str) -> str | None:
        url = self._client.build_service_url(f"{_BUNDLE_PATH}/{bundle_id}")
        response = await self._client.request_with_retry("GET", url, non_retryable_statuses={404})
        if response is None:
            return None
        _, composition_id = sender.extrair_ids_resposta(response)
        return composition_id

    async def get_documento(self, id_rnds: str) -> dict[str, Any]:
        url = self._client.build_service_url(f"{_BUNDLE_PATH}/{id_rnds}")
        response = await self._client.request_with_retry("GET", url)
        return response.json() if response else {}

    async def deletar_documento(self, id_rnds: str) -> None:
        url = self._client.build_service_url(f"{_BUNDLE_PATH}/{id_rnds}")
        await self._client.request("DELETE", url)

    def dump_bundle_json(
        self,
        dados: RiraDocumentData,
        composition_status: str,
        predecessor_composition_id: str | None = None,
    ) -> str:
        return sender.dump_bundle_json(dados, composition_status, predecessor_composition_id)


def _ids_do_documento_consulta(item: dict) -> tuple[str | None, str | None]:
    id_direto = item.get("idRNDS") or item.get("id_rnds") or item.get("id")
    if item.get("resourceType") != "Bundle":
        return id_direto, None
    composition_id = None
    for entry in item.get("entry", []) or []:
        recurso = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(recurso, dict) and recurso.get("resourceType") == "Composition":
            composition_id = recurso.get("id")
            break
    return id_direto, composition_id


def _com_identifier_system(settings: RiraFhirSettings, identifier_system: str) -> RiraFhirSettings:
    return replace(settings, bundle_id_system_override=identifier_system)


def _com_id_local(dados: RiraDocumentData, identificador_local: str) -> RiraDocumentData:
    if dados.id_local == identificador_local:
        return dados
    return replace(dados, id_local=identificador_local)
