import asyncio
import os
import unittest

os.environ.update(
    {
        "RIRA_NAMING_SYSTEM_ID": "9999",
        "RIRA_COMP_PROFILE": "http://test/comp",
        "RIRA_SR_PROFILE": "http://test/sr",
        "RIRA_APP_PROFILE": "http://test/app",
        "RIRA_COND_PROFILE": "http://test/cond",
    }
)

import httpx  # noqa: E402

from rnds_client.rira.exceptions import (  # noqa: E402
    ErroRiraRejeitado,
    ErroRiraTransitorio,
    ResultadoRiraIncerto,
    RiraValidationError,
)
from rnds_client.rira.schemas.rira_document import RiraDocumentData  # noqa: E402
from rnds_client.rira.services.sender import (  # noqa: E402
    classificar_erro_http,
    extrair_ids_resposta,
    montar_bundle,
)
from rnds_client.rira.settings import RiraFhirSettings  # noqa: E402


def _req():
    return httpx.Request("POST", "https://x/api/fhir/r4/Bundle")


def _status_error(status, headers=None):
    resp = httpx.Response(status, headers=headers or {}, request=_req())
    return httpx.HTTPStatusError("erro", request=_req(), response=resp)


class TestClassificacaoErro(unittest.TestCase):
    def test_timeout_antes_do_post_e_transitorio(self):
        erro = classificar_erro_http(httpx.ReadTimeout("t", request=_req()))
        self.assertIsInstance(erro, ErroRiraTransitorio)
        self.assertEqual(erro.codigo, "timeout")

    def test_timeout_apos_post_e_incerto(self):
        erro = classificar_erro_http(httpx.ReadTimeout("t", request=_req()), apos_post=True)
        self.assertIsInstance(erro, ResultadoRiraIncerto)

    def test_429_transitorio_com_retry_after(self):
        erro = classificar_erro_http(_status_error(429, {"Retry-After": "42"}))
        self.assertIsInstance(erro, ErroRiraTransitorio)
        self.assertEqual(erro.retry_after, 42)

    def test_5xx_transitorio(self):
        self.assertIsInstance(classificar_erro_http(_status_error(503)), ErroRiraTransitorio)

    def test_4xx_funcional_rejeitado(self):
        erro = classificar_erro_http(_status_error(422))
        self.assertIsInstance(erro, ErroRiraRejeitado)
        self.assertEqual(erro.http_status, 422)

    def test_validacao_local_rejeitada_por_completude(self):
        erro = classificar_erro_http(RiraValidationError("CBO ausente"))
        self.assertIsInstance(erro, ErroRiraRejeitado)
        self.assertEqual(erro.codigo, "completude")


class TestExtrairIdsResposta(unittest.TestCase):
    def test_bundle_id_e_composition_id_sao_distintos(self):
        corpo = {
            "resourceType": "Bundle",
            "id": "4a31-i0b0",
            "entry": [
                {"resource": {"resourceType": "Composition", "id": "a1a8-c0m1"}},
                {"resource": {"resourceType": "Appointment", "id": "zzz"}},
            ],
        }
        resp = httpx.Response(201, json=corpo, request=_req())
        bundle_id, composition_id = extrair_ids_resposta(resp)
        self.assertEqual(bundle_id, "4a31-i0b0")
        self.assertEqual(composition_id, "a1a8-c0m1")
        self.assertNotEqual(bundle_id, composition_id)


class _BaseClientStub:
    def __init__(self, response):
        self._response = response
        self.chamadas = []

    def build_service_url(self, path):
        return f"https://x/api/{path}"

    async def request(self, method, url, **kwargs):
        self.chamadas.append((method, url, kwargs))
        return self._response

    async def request_with_retry(self, method, url, **kwargs):
        return self._response


def _dados(**kwargs):
    defaults = dict(
        id_local="item-1",
        id_paciente="12345678901",
        sigtap="0101010010",
        cid10="J180",
        data_solicitacao="2024-01-15T10:00:00-03:00",
        cnes_solicitante="1234567",
        modalidade="09",
        carater="routine",
    )
    defaults.update(kwargs)
    return RiraDocumentData(**defaults)


class TestEnviarRira(unittest.TestCase):
    def test_devolve_location_bruto_e_ids_separados(self):
        from rnds_client.capabilities.rira import RiraCapability

        corpo = {
            "resourceType": "Bundle",
            "id": "4a31-i0b0",
            "entry": [{"resource": {"resourceType": "Composition", "id": "a1a8-c0m1"}}],
        }
        resp = httpx.Response(
            201,
            json=corpo,
            headers={"location": "https://mg-ehr-services/api/fhir/r4/Bundle/4a31-i0b0"},
            request=_req(),
        )
        cap = RiraCapability(_BaseClientStub(resp))
        resultado = asyncio.run(cap.enviar_rira(_dados(), "item-1", status_rira="pending"))
        self.assertEqual(resultado.http_status, 201)
        self.assertEqual(
            resultado.location_rnds, "https://mg-ehr-services/api/fhir/r4/Bundle/4a31-i0b0"
        )
        self.assertEqual(resultado.id_rnds_bundle, "4a31-i0b0")
        self.assertEqual(resultado.id_rnds_composition, "a1a8-c0m1")

    def test_predecessor_gera_relatesto_no_bundle(self):
        from rnds_client.capabilities.rira import RiraCapability

        resp = httpx.Response(
            201,
            json={"id": "novo", "entry": [{"resource": {"resourceType": "Composition", "id": "novo-c"}}]},
            headers={"location": "https://x/Bundle/novo"},
            request=_req(),
        )
        stub = _BaseClientStub(resp)
        cap = RiraCapability(stub)
        asyncio.run(
            cap.enviar_rira(
                _dados(data_agendamento="2024-01-20T09:00:00-03:00"),
                "item-1",
                status_rira="booked",
                predecessor_composition_id="ant-c0m1",
                identifier_system="http://ns/BRRNDS-52150",
            )
        )
        import json

        enviado = json.loads(stub.chamadas[0][2]["content"])
        composition = enviado["entry"][0]["resource"]
        self.assertEqual(composition["relatesTo"][0]["code"], "replaces")
        self.assertEqual(
            composition["relatesTo"][0]["targetReference"]["reference"], "Composition/ant-c0m1"
        )
        self.assertEqual(enviado["identifier"]["system"], "http://ns/BRRNDS-52150")

    def test_status_invalido_levanta_value_error(self):
        from rnds_client.capabilities.rira import RiraCapability

        cap = RiraCapability(_BaseClientStub(httpx.Response(201, request=_req())))
        with self.assertRaises(ValueError):
            asyncio.run(cap.enviar_rira(_dados(), "item-1", status_rira="faltou"))


def _service_request(bundle: dict) -> dict:
    for entry in bundle["entry"]:
        recurso = entry.get("resource", {})
        if recurso.get("resourceType") == "ServiceRequest":
            return recurso
    raise AssertionError("Bundle sem ServiceRequest")


class TestServiceRequestStatus(unittest.TestCase):
    """Regressão do mira-16: attended exige ServiceRequest.status='completed'."""

    def setUp(self):
        self.settings = RiraFhirSettings.from_environment()

    def test_attended_gera_service_request_completed(self):
        bundle = montar_bundle(
            _dados(
                data_agendamento="2024-01-20T09:00:00-03:00",
                data_atendimento="2024-01-20T10:00:00-03:00",
            ),
            self.settings,
            "attended",
        )
        self.assertEqual(_service_request(bundle)["status"], "completed")

    def test_pending_gera_service_request_active(self):
        bundle = montar_bundle(_dados(), self.settings, "pending")
        self.assertEqual(_service_request(bundle)["status"], "active")

    def test_booked_gera_service_request_active(self):
        bundle = montar_bundle(
            _dados(data_agendamento="2024-01-20T09:00:00-03:00"), self.settings, "booked"
        )
        self.assertEqual(_service_request(bundle)["status"], "active")


class TestConsultarRira(unittest.TestCase):
    """Regressão: consultar_rira usa GET .../identifier?system&value&docType=RA (manual §8.2)."""

    def _resposta_identifier(self):
        corpo = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Composition",
                        "id": "a1a8-c0m1",
                    }
                }
            ],
        }
        return httpx.Response(200, json=corpo, request=httpx.Request("GET", "https://x/api/identifier"))

    def test_consulta_bate_no_endpoint_identifier_com_parametros(self):
        from rnds_client.capabilities.rira import RiraCapability

        capturado = {}

        class _Stub:
            def build_service_url(self, path):
                return f"https://x/api/{path}"

            async def request_with_retry(self, method, url, **kwargs):
                capturado["method"] = method
                capturado["url"] = url
                capturado["params"] = kwargs.get("params")
                return _resp

        _resp = self._resposta_identifier()
        cap = RiraCapability(_Stub())
        resultados = asyncio.run(
            cap.consultar_rira("http://ns/BRRNDS-9999", "item-1")
        )

        self.assertEqual(capturado["method"], "GET")
        self.assertTrue(capturado["url"].endswith("/identifier"))
        self.assertEqual(
            capturado["params"],
            {"system": "http://ns/BRRNDS-9999", "value": "item-1", "docType": "RA"},
        )
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0].id_rnds_composition, "a1a8-c0m1")

    def test_consulta_sem_corpo_devolve_lista_vazia(self):
        from rnds_client.capabilities.rira import RiraCapability

        class _Stub:
            def build_service_url(self, path):
                return f"https://x/api/{path}"

            async def request_with_retry(self, method, url, **kwargs):
                return httpx.Response(404, request=httpx.Request("GET", url))

        cap = RiraCapability(_Stub())
        self.assertEqual(
            asyncio.run(cap.consultar_rira("http://ns/BRRNDS-9999", "sumiu")), []
        )


if __name__ == "__main__":
    unittest.main()
