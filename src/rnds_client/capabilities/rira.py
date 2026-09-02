from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from httpx import HTTPError

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

        settings = RiraFhirSettings.from_environment()
        if identifier_system:
            settings = _com_identifier_system(settings, identifier_system)

        dados = _com_id_local(dados, identificador_local)

        try:
            bundle_dict = sender.montar_bundle(
                dados, settings, composition_status, predecessor_composition_id
            )
        except Exception as exc:
            raise sender.classificar_erro_http(exc) from exc

        url = self._client.build_service_url(_BUNDLE_PATH)
        try:
            response = await self._client.request(
                "POST", url, content=json.dumps(bundle_dict, ensure_ascii=False).encode()
            )
        except HTTPError as exc:
            raise sender.classificar_erro_http(exc, apos_post=True) from exc

        location = response.headers.get("location", "")
        bundle_id, composition_id = sender.extrair_ids_resposta(response)

        if not bundle_id and location:
            bundle_id = sender.extrair_id_rnds(location)
        if not composition_id and bundle_id:
            composition_id = await self._composition_id_por_get(bundle_id)

        if not location and not bundle_id:
            raise ResultadoRiraIncerto(
                "POST aceito mas sem Location nem corpo utilizável.", codigo="resposta_perdida"
            )

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
            rnds_id = item.get("idRNDS") or item.get("id_rnds") or item.get("id")
            location = item.get("location") or item.get("url")
            if not rnds_id and location:
                rnds_id = location.rstrip("/").split("/")[-1]
            if not rnds_id:
                continue
            resultados.append(
                ResultadoEnvioRira(
                    http_status=response.status_code,
                    location_rnds=location,
                    id_rnds_bundle=rnds_id,
                    id_rnds_composition=rnds_id,
                )
            )
        return resultados

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


def _com_identifier_system(settings: RiraFhirSettings, identifier_system: str) -> RiraFhirSettings:
    return replace(settings, bundle_id_system_override=identifier_system)


def _com_id_local(dados: RiraDocumentData, identificador_local: str) -> RiraDocumentData:
    if dados.id_local == identificador_local:
        return dados
    return replace(dados, id_local=identificador_local)
