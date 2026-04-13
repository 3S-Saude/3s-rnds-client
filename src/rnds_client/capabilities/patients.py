from __future__ import annotations

from typing import Any

from rnds_client.base_client import RndsBaseClient
from rnds_client.parsers import format_patient_payload


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

    def _person_url(self, query_parameter: str) -> str:
        return self._client.build_service_url(
            f"fhir/r4/Patient?identifier=http://rnds.saude.gov.br/fhir/r4/NamingSystem/{query_parameter}"
        )

    @staticmethod
    def _query_parameter(identificador: str) -> str | None:
        identificador_limpo = identificador.replace(".", "").replace("-", "")
        if len(identificador_limpo) == 11:
            return f"cpf%7C{identificador_limpo}"
        if len(identificador_limpo) > 11:
            return f"cns%7C{identificador_limpo}"
        return None

