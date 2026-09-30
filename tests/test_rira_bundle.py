import os
import unittest
from unittest import mock

_RIRA_ENV = {
    "RIRA_NAMING_SYSTEM_ID": "9999",
    "RIRA_CNES_AUTOR": "1234567",
}
os.environ.update(_RIRA_ENV)

from rnds_client.rira.codesystems import (  # noqa: E402
    CID10_SYSTEM,
    CNES_SYSTEM,
    INDIVIDUO_SYSTEM,
    SIGTAP_SYSTEM,
    STATUS_REGULACAO_SYSTEM,
    TIPO_DOCUMENTO_SYSTEM,
)
from rnds_client.rira.schemas.rira_document import RiraDocumentData  # noqa: E402
from rnds_client.rira.services.sender import montar_bundle  # noqa: E402
from rnds_client.rira.settings import RiraFhirSettings  # noqa: E402

_SETTINGS = RiraFhirSettings.from_environment()
_DATA_AGENDAMENTO = "2024-01-20T09:00:00-03:00"
_PERFIS_CANONICOS = {
    "Composition": ["http://www.saude.gov.br/fhir/r4/StructureDefinition/BRRegulacaoAssistencial"],
    "ServiceRequest": ["http://www.saude.gov.br/fhir/r4/StructureDefinition/BRRequisicaoRegulacaoAssistencial"],
    "Appointment": ["http://www.saude.gov.br/fhir/r4/StructureDefinition/BRAgendamentoRegulacaoAssistencial"],
    "Condition": ["http://www.saude.gov.br/fhir/r4/StructureDefinition/BRCID10Avaliado-1.0"],
}


def _dados(**kwargs) -> RiraDocumentData:
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


def _bundle(**kwargs) -> dict:
    status = kwargs.pop("_status", "pending")
    predecessor = kwargs.pop("_predecessor_composition_id", None)
    return montar_bundle(_dados(**kwargs), _SETTINGS, status, predecessor)


def _comp(**kwargs) -> dict:
    return _bundle(**kwargs)["entry"][0]["resource"]


def _resource(resource_type: str, **kwargs) -> dict:
    return next(
        e["resource"]
        for e in _bundle(**kwargs)["entry"]
        if e["resource"]["resourceType"] == resource_type
    )


def _perfis(bundle: dict) -> dict:
    return {
        entrada["resource"]["resourceType"]: entrada["resource"]["meta"]["profile"]
        for entrada in bundle["entry"]
    }


class TestEstruturaBundle(unittest.TestCase):

    def setUp(self):
        self.bundle = _bundle()

    def test_resource_type_bundle(self):
        self.assertEqual(self.bundle["resourceType"], "Bundle")

    def test_bundle_type_document(self):
        self.assertEqual(self.bundle["type"], "document")

    def test_bundle_tem_meta_last_updated(self):
        self.assertIn("lastUpdated", self.bundle["meta"])

    def test_tem_4_entries(self):
        self.assertEqual(len(self.bundle["entry"]), 4)

    def test_fullurls_na_ordem_correta(self):
        urls = [e["fullUrl"] for e in self.bundle["entry"]]
        self.assertEqual(urls[0], "urn:uuid:transient-0")
        self.assertEqual(urls[1], "urn:uuid:transient-1")
        self.assertEqual(urls[2], "urn:uuid:transient-2")
        self.assertEqual(urls[3], "urn:uuid:transient-3")

    def test_resource_types_das_entries(self):
        types = [e["resource"]["resourceType"] for e in self.bundle["entry"]]
        self.assertIn("Composition", types)
        self.assertIn("Appointment", types)
        self.assertIn("ServiceRequest", types)
        self.assertIn("Condition", types)

    def test_composition_status_final(self):
        self.assertEqual(self.bundle["entry"][0]["resource"]["status"], "final")

    def test_bundle_identifier_usa_id_local(self):
        self.assertEqual(self.bundle["identifier"]["value"], "item-1")

    def test_perfis_canonicos_sem_variaveis_de_ambiente(self):
        with mock.patch.dict(os.environ, _RIRA_ENV, clear=True):
            configuracao = RiraFhirSettings.from_environment()
            bundle = montar_bundle(_dados(), configuracao, "pending")

        self.assertEqual(_perfis(bundle), _PERFIS_CANONICOS)
        self.assertEqual(
            bundle["identifier"]["system"],
            "http://www.saude.gov.br/fhir/r4/NamingSystem/BRRNDS-9999",
        )

    def test_variaveis_antigas_nao_alteram_perfis(self):
        ambiente = {
            **_RIRA_ENV,
            "RIRA_COMP_PROFILE": "http://test/comp",
            "RIRA_SR_PROFILE": "http://test/sr",
            "RIRA_APP_PROFILE": "http://test/app",
            "RIRA_COND_PROFILE": "http://test/cond",
        }
        with mock.patch.dict(os.environ, ambiente, clear=True):
            configuracao = RiraFhirSettings.from_environment()
            bundle = montar_bundle(_dados(), configuracao, "pending")
        self.assertEqual(_perfis(bundle), _PERFIS_CANONICOS)

    def test_identificador_system_explicito_dispensa_naming_no_ambiente(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            configuracao = RiraFhirSettings.from_environment(
                bundle_id_system_override="http://test/naming-system"
            )
        self.assertEqual(configuracao.bundle_id_system, "http://test/naming-system")

    def test_construcao_explicita_permanece_compativel(self):
        configuracao = RiraFhirSettings(
            naming_system_id="9999",
            comp_profile="http://test/comp",
            sr_profile="http://test/sr",
            app_profile="http://test/app",
            cond_profile="http://test/cond",
        )
        self.assertEqual(configuracao.comp_profile, "http://test/comp")


class TestCamposDeNegocio(unittest.TestCase):

    def test_paciente_cpf_usa_system_fixo_individuo(self):
        comp = _comp(id_paciente="12345678901")
        self.assertEqual(comp["subject"]["identifier"]["system"], INDIVIDUO_SYSTEM)

    def test_paciente_cns_usa_system_fixo_individuo(self):
        comp = _comp(id_paciente="123456789012345")
        self.assertEqual(comp["subject"]["identifier"]["system"], INDIVIDUO_SYSTEM)

    def test_author_usa_cnes_system(self):
        comp = _comp()
        self.assertEqual(comp["author"][0]["identifier"]["system"], CNES_SYSTEM)

    def test_condition_tem_cid10_e_system_correto(self):
        cond = _resource("Condition")
        coding = cond["code"]["coding"][0]
        self.assertEqual(coding["code"], "J180")
        self.assertEqual(coding["system"], CID10_SYSTEM)

    def test_condition_note_usa_observacao_informada(self):
        cond = _resource("Condition", observacao="Dor lombar cronica.")
        self.assertEqual(cond["note"][0]["text"], "Dor lombar cronica.")

    def test_condition_note_usa_padrao_quando_ausente(self):
        cond = _resource("Condition")
        self.assertEqual(cond["note"][0]["text"], "Sem observações")

    def test_service_request_tem_sigtap_e_system_correto(self):
        sr = _resource("ServiceRequest")
        coding = sr["code"]["coding"][0]
        self.assertEqual(coding["code"], "0101010010")
        self.assertEqual(coding["system"], SIGTAP_SYSTEM)

    def test_composition_tipo_documento_ra(self):
        comp = _comp()
        coding = comp["type"]["coding"][0]
        self.assertEqual(coding["code"], "RA")
        self.assertEqual(coding["system"], TIPO_DOCUMENTO_SYSTEM)

    def test_composition_event_code_pending(self):
        comp = _comp()
        coding = comp["event"][0]["code"][0]["coding"][0]
        self.assertEqual(coding["code"], "pending")
        self.assertEqual(coding["system"], STATUS_REGULACAO_SYSTEM)

    def test_composition_event_code_booked(self):
        comp = _comp(_status="booked", id_local="item-ev-booked", data_agendamento=_DATA_AGENDAMENTO)
        coding = comp["event"][0]["code"][0]["coding"][0]
        self.assertEqual(coding["code"], "booked")


class TestStatusPorRegulacao(unittest.TestCase):

    _CASOS = {
        "pending": ("proposed", "active"),
        "booked": ("booked", "active"),
        "attended": ("fulfilled", "completed"),
        "absence": ("noshow", "completed"),
        "cancelled": ("cancelled", "revoked"),
        "returned-to-requester": ("waitlist", "on-hold"),
    }

    def _bundle_do_status(self, status: str) -> dict:
        extra = {}
        if status in ("booked", "attended", "absence"):
            extra["data_agendamento"] = _DATA_AGENDAMENTO
        return _bundle(_status=status, id_local=f"item-{status}", **extra)

    def test_appointment_e_service_request_status(self):
        for status, (appt_esperado, sr_esperado) in self._CASOS.items():
            with self.subTest(status=status):
                bundle = self._bundle_do_status(status)
                appt = next(
                    e["resource"] for e in bundle["entry"]
                    if e["resource"]["resourceType"] == "Appointment"
                )
                sr = next(
                    e["resource"] for e in bundle["entry"]
                    if e["resource"]["resourceType"] == "ServiceRequest"
                )
                self.assertEqual(appt["status"], appt_esperado)
                self.assertEqual(sr["status"], sr_esperado)

    def test_falta_referencia_o_agendamento_no_evento(self):
        bundle = self._bundle_do_status("absence")
        comp = bundle["entry"][0]["resource"]
        self.assertEqual(comp["event"][0]["code"][0]["coding"][0]["code"], "absence")
        self.assertTrue(any("reference" in detalhe for detalhe in comp["event"][0]["detail"]))

    def test_returned_to_requester_dispensa_datas_no_appointment(self):
        bundle = self._bundle_do_status("returned-to-requester")
        appt = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Appointment"
        )
        self.assertNotIn("start", appt)


class TestCboPorEstado(unittest.TestCase):
    def test_cancelamento_sem_cbo_preserva_recursos_e_substituicao(self):
        for sigtap in ("0301010010", "0401010015"):
            for predecessor in (None, "composition-anterior"):
                with self.subTest(sigtap=sigtap, predecessor=predecessor):
                    bundle = _bundle(
                        _status="cancelled", sigtap=sigtap,
                        _predecessor_composition_id=predecessor,
                    )
                    recursos = {e["resource"]["resourceType"]: e["resource"] for e in bundle["entry"]}
                    self.assertEqual(len(recursos), 4)
                    self.assertEqual(recursos["ServiceRequest"]["status"], "revoked")
                    self.assertEqual(recursos["Appointment"]["status"], "cancelled")
                    self.assertNotIn("performerType", recursos["ServiceRequest"])
                    self.assertNotIn("specialty", recursos["Appointment"])
                    composition = recursos["Composition"]
                    self.assertEqual(composition["event"][0]["code"][0]["coding"][0]["code"], "cancelled")
                    self.assertEqual(composition["section"][0]["entry"][0]["reference"], "urn:uuid:transient-1")
                    if predecessor:
                        self.assertEqual(composition["relatesTo"][0]["targetReference"]["reference"], f"Composition/{predecessor}")
                    else:
                        self.assertNotIn("relatesTo", composition)

    def test_cancelamento_preserva_cbo_informado_em_ambos_os_recursos(self):
        for sigtap in ("0301010010", "0401010015"):
            with self.subTest(sigtap=sigtap):
                bundle = _bundle(_status="cancelled", sigtap=sigtap, cbo_executante="225125")
                recursos = {e["resource"]["resourceType"]: e["resource"] for e in bundle["entry"]}
                self.assertEqual(recursos["ServiceRequest"]["performerType"]["coding"][0]["code"], "225125")
                self.assertEqual(recursos["Appointment"]["specialty"][0]["coding"][0]["code"], "225125")

    def test_demais_estados_exigem_cbo_nos_grupos_03_04(self):
        for status in ("pending", "booked", "attended", "absence", "returned-to-requester"):
            for sigtap in ("0301010010", "0401010015"):
                with self.subTest(status=status, sigtap=sigtap):
                    with self.assertRaisesRegex(ValueError, "CBO obrigatório"):
                        _bundle(_status=status, sigtap=sigtap, data_agendamento=_DATA_AGENDAMENTO)


class TestAppointmentExigeDatas(unittest.TestCase):

    def test_pending_nao_exige_data_agendamento(self):
        appointment = _resource("Appointment", id_local="appt-pending")
        self.assertNotIn("start", appointment)

    def test_booked_sem_data_agendamento_ou_autorizacao_falha(self):
        with self.assertRaises(Exception):
            _resource("Appointment", _status="booked", id_local="appt-booked-invalido")

    def test_attended_sem_data_agendamento_ou_autorizacao_falha(self):
        with self.assertRaises(Exception):
            _resource("Appointment", _status="attended", id_local="appt-attended-invalido")

    def test_booked_com_data_agendamento_funciona(self):
        appointment = _resource(
            "Appointment",
            _status="booked",
            id_local="appt-booked-valido",
            data_agendamento=_DATA_AGENDAMENTO,
        )
        self.assertEqual(appointment["start"], _DATA_AGENDAMENTO)
        self.assertIsNotNone(appointment["end"])


class TestLogicaSubstituicao(unittest.TestCase):

    def test_sem_predecessor_nao_tem_relates_to(self):
        comp = _comp(id_local="sub-zero")
        self.assertNotIn("relatesTo", comp)

    def test_com_predecessor_tem_relates_to_replaces(self):
        comp = _comp(
            id_local="sub-dois",
            _status="booked",
            _predecessor_composition_id="a1a8-c0m1",
            data_agendamento=_DATA_AGENDAMENTO,
        )
        self.assertIn("relatesTo", comp)
        relates = comp["relatesTo"][0]
        self.assertEqual(relates["code"], "replaces")
        self.assertEqual(
            relates["targetReference"]["reference"],
            "Composition/a1a8-c0m1",
        )

    def test_predecessor_nulo_nao_gera_relates_to(self):
        comp = _comp(
            id_local="sub-sem-historico",
            _status="booked",
            _predecessor_composition_id=None,
            data_agendamento=_DATA_AGENDAMENTO,
        )
        self.assertNotIn("relatesTo", comp)


if __name__ == "__main__":
    unittest.main()
