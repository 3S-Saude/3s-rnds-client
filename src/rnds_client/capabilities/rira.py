from __future__ import annotations

import json
from typing import Any

from rnds_client.base_client import RndsBaseClient
from rnds_client.rira.schemas.rira_document import RiraDocumentData
from rnds_client.rira.services import sender
from rnds_client.rira.settings import RiraFhirSettings

_BUNDLE_PATH = "fhir/r4/Bundle"


class RiraCapability:
    def __init__(self, client: RndsBaseClient) -> None:
        self._client = client

    async def criar_documento_pending(self, dados: RiraDocumentData) -> str:
        return await self._enviar(dados, "pending")

    async def criar_documento_booked(self, dados: RiraDocumentData) -> str:
        return await self._enviar(dados, "booked")

    async def criar_documento_attended(self, dados: RiraDocumentData) -> str:
        return await self._enviar(dados, "attended")

    async def criar_documento_returned_to_requester(self, dados: RiraDocumentData) -> str:
        return await self._enviar(dados, "returned-to-requester")

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
        id_rnds_anterior: str | None = None,
    ) -> str:
        return sender.dump_bundle_json(dados, composition_status, id_rnds_anterior)

    async def _enviar(self, dados: RiraDocumentData, composition_status: str) -> str:
        settings = RiraFhirSettings.from_environment()
        id_rnds_anterior = await sender.buscar_id_rnds_anterior(dados.id_local)
        bundle_dict = sender.montar_bundle(dados, settings, composition_status, id_rnds_anterior)
        url = self._client.build_service_url(_BUNDLE_PATH)

        response = await self._client.request(
            "POST",
            url,
            content=json.dumps(bundle_dict, ensure_ascii=False).encode(),
        )

        id_rnds = sender.extrair_id_rnds(response.headers.get("location", ""))
        await sender.salvar_envio(dados.id_local, id_rnds, composition_status)
        return id_rnds
