from __future__ import annotations

from typing import Any

from rnds_client.base_client import RndsBaseClient
from rnds_client.parsers import format_organization_payload


class EstablishmentsCapability:
    def __init__(self, client: RndsBaseClient) -> None:
        self._client = client

    async def buscar_cnes(self, cnes: str) -> dict[str, Any] | None:
        cnes_limpo = self._normalize_cnes(cnes)
        if cnes_limpo is None:
            return None

        response = await self._client.request_with_retry(
            "GET",
            self._organization_url(cnes_limpo),
            non_retryable_statuses={400, 404},
        )
        if response is None:
            return None

        payload = response.json()
        return format_organization_payload(payload) if isinstance(payload, dict) else None

    def _organization_url(self, cnes: str) -> str:
        return self._client.build_service_url(f"fhir/r4/Organization/{cnes}")

    @staticmethod
    def _normalize_cnes(cnes: str) -> str | None:
        cnes_limpo = "".join(character for character in cnes if character.isdigit())
        return cnes_limpo or None
