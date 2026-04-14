import unittest
from httpx import Response

from rnds_client.capabilities.establishments import EstablishmentsCapability


class _FakeBaseClient:
    def __init__(self, response: Response | None) -> None:
        self.response = response
        self.calls: list[tuple[str, str, set[int] | None]] = []

    async def request_with_retry(
        self,
        method: str,
        url: str,
        *,
        non_retryable_statuses: set[int] | None = None,
        **kwargs: object,
    ) -> Response | None:
        self.calls.append((method, url, non_retryable_statuses))
        return self.response

    def build_service_url(self, path: str) -> str:
        return f"https://service.example/{path}"


class EstablishmentsCapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_busca_cnes_uses_organization_endpoint(self) -> None:
        base_client = _FakeBaseClient(
            Response(
                200,
                json={
                    "resourceType": "Organization",
                    "id": "1234567",
                    "name": "Hospital Teste",
                    "active": True,
                    "type": [{"coding": [{"display": "HOSPITAL"}]}],
                    "telecom": [{"system": "phone", "value": "6533330000"}],
                    "address": [{"line": ["Rua A", "123"], "district": "Centro", "postalCode": "78000000"}],
                },
            )
        )
        capability = EstablishmentsCapability(base_client)  # type: ignore[arg-type]

        result = await capability.buscar_cnes("1234567")

        self.assertEqual(
            result,
            {
                "nome": "Hospital Teste",
                "telefone": "6533330000",
                "email": None,
                "ativo": True,
                "tipo": "HOSPITAL",
                "ibge": None,
                "logradouro": "Rua A",
                "bairro": "Centro",
                "numero": "123",
                "complemento": None,
                "cep": "78000000",
            },
        )
        self.assertEqual(
            base_client.calls,
            [("GET", "https://service.example/fhir/r4/Organization/1234567", {400, 404})],
        )

    async def test_busca_cnes_normalizes_digits(self) -> None:
        base_client = _FakeBaseClient(Response(200, json={"id": "1234567"}))
        capability = EstablishmentsCapability(base_client)  # type: ignore[arg-type]

        await capability.buscar_cnes("12.345-67")

        self.assertEqual(
            base_client.calls,
            [("GET", "https://service.example/fhir/r4/Organization/1234567", {400, 404})],
        )

    async def test_busca_cnes_returns_none_when_identifier_is_empty(self) -> None:
        base_client = _FakeBaseClient(Response(200, json={"id": "ignored"}))
        capability = EstablishmentsCapability(base_client)  # type: ignore[arg-type]

        result = await capability.buscar_cnes("---")

        self.assertIsNone(result)
        self.assertEqual(base_client.calls, [])

    async def test_busca_cnes_returns_none_when_service_returns_none(self) -> None:
        base_client = _FakeBaseClient(None)
        capability = EstablishmentsCapability(base_client)  # type: ignore[arg-type]

        result = await capability.buscar_cnes("1234567")

        self.assertIsNone(result)
