import asyncio
import os
import unittest

import django
from django.conf import settings as dj

_RIRA_ENV = {
    "RIRA_NAMING_SYSTEM_ID": "9999",
    "RIRA_CNES_AUTOR": "1234567",
    "RIRA_COMP_PROFILE": "http://test/comp",
    "RIRA_SR_PROFILE": "http://test/sr",
    "RIRA_APP_PROFILE": "http://test/app",
    "RIRA_COND_PROFILE": "http://test/cond",
}
os.environ.update(_RIRA_ENV)
dj.configure(
    INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "rnds_client.rira"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
)
django.setup()

from django.core.management import call_command  # noqa: E402

call_command("migrate", "--run-syncdb", verbosity=0)

from rnds_client.rira.codesystems import (  # noqa: E402
    CID10_SYSTEM,
    CNES_SYSTEM,
    INDIVIDUO_SYSTEM,
    SIGTAP_SYSTEM,
    STATUS_REGULACAO_SYSTEM,
    TIPO_DOCUMENTO_SYSTEM,
)
from rnds_client.rira.schemas.rira_document import RiraDocumentData  # noqa: E402
from rnds_client.rira.services.sender import (  # noqa: E402
    buscar_id_rnds_anterior,
    montar_bundle,
    salvar_envio,
)
from rnds_client.rira.settings import RiraFhirSettings  # noqa: E402

_SETTINGS = RiraFhirSettings.from_environment()
_DATA_AGENDAMENTO = "2024-01-20T09:00:00-03:00"


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
    id_rnds_anterior = kwargs.pop("_id_rnds_anterior", None)
    return montar_bundle(_dados(**kwargs), _SETTINGS, status, id_rnds_anterior)


def _comp(**kwargs) -> dict:
    return _bundle(**kwargs)["entry"][0]["resource"]


def _resource(resource_type: str, **kwargs) -> dict:
    return next(
        e["resource"]
        for e in _bundle(**kwargs)["entry"]
        if e["resource"]["resourceType"] == resource_type
    )


def _salvar_envio_sync(id_local: str, id_rnds: str, status: str) -> None:
    asyncio.run(salvar_envio(id_local, id_rnds, status))


def _buscar_id_rnds_anterior_sync(id_local: str) -> str | None:
    return asyncio.run(buscar_id_rnds_anterior(id_local))


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
        self.assertEqual(urls[0], "urn:uuid:transient-0")  # Composition
        self.assertEqual(urls[1], "urn:uuid:transient-1")  # Appointment
        self.assertEqual(urls[2], "urn:uuid:transient-2")  # ServiceRequest
        self.assertEqual(urls[3], "urn:uuid:transient-3")  # Condition

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


class TestCamposDeNegocio(unittest.TestCase):

    def test_paciente_cpf_usa_system_fixo_individuo(self):
        comp = _comp(id_paciente="12345678901")
        self.assertEqual(comp["subject"]["identifier"]["system"], INDIVIDUO_SYSTEM)

    def test_paciente_cns_usa_system_fixo_individuo(self):
        # O manual (item 8.1, comentário sobre "subject") define que o system e
        # fixo independentemente do valor ser CPF ou CNS.
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


class TestAppointmentExigeDatas(unittest.TestCase):

    def test_pending_nao_exige_data_agendamento(self):
        appointment = _resource("Appointment", id_local="appt-pending")
        self.assertIsNone(appointment["start"])

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

    def test_primeiro_envio_sem_relates_to(self):
        comp = _comp(id_local="sub-zero")
        self.assertNotIn("relatesTo", comp)

    def test_segundo_envio_tem_relates_to(self):
        _salvar_envio_sync("sub-dois", "uuid-rnds-anterior-abc", "pending")
        id_rnds_anterior = _buscar_id_rnds_anterior_sync("sub-dois")
        comp = _comp(
            id_local="sub-dois",
            _status="booked",
            _id_rnds_anterior=id_rnds_anterior,
            data_agendamento=_DATA_AGENDAMENTO,
        )
        self.assertIn("relatesTo", comp)
        relates = comp["relatesTo"][0]
        self.assertEqual(relates["code"], "replaces")
        self.assertEqual(
            relates["targetReference"]["reference"],
            "Composition/uuid-rnds-anterior-abc",
        )

    def test_relates_to_aponta_para_ultimo_id_rnds(self):
        _salvar_envio_sync("sub-tres", "primeiro-id", "pending")
        _salvar_envio_sync("sub-tres", "segundo-id", "booked")  # atualiza o mesmo id_local
        id_rnds_anterior = _buscar_id_rnds_anterior_sync("sub-tres")
        comp = _comp(
            id_local="sub-tres",
            _status="attended",
            _id_rnds_anterior=id_rnds_anterior,
            data_agendamento=_DATA_AGENDAMENTO,
        )
        ref = comp["relatesTo"][0]["targetReference"]["reference"]
        self.assertEqual(ref, "Composition/segundo-id")

    def test_ids_locais_distintos_nao_interferem(self):
        _salvar_envio_sync("sub-outro", "id-de-outro-item", "pending")
        id_rnds_anterior = _buscar_id_rnds_anterior_sync("sub-sem-historico")
        comp = _comp(
            id_local="sub-sem-historico",
            _status="booked",
            _id_rnds_anterior=id_rnds_anterior,
            data_agendamento=_DATA_AGENDAMENTO,
        )
        self.assertNotIn("relatesTo", comp)


if __name__ == "__main__":
    unittest.main()
