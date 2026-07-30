from __future__ import annotations

import json
from datetime import datetime, timezone

from rnds_client.rira.codesystems import FULLURL_APPOINTMENT, FULLURL_CONDITION, FULLURL_SERVICE_REQUEST
from rnds_client.rira.schemas.fhir.appointment import Appointment
from rnds_client.rira.schemas.fhir.bundle import Bundle
from rnds_client.rira.schemas.fhir.composition import Composition
from rnds_client.rira.schemas.fhir.condition import Condition
from rnds_client.rira.schemas.fhir.service_request import ServiceRequest
from rnds_client.rira.schemas.rira_document import RiraDocumentData
from rnds_client.rira.settings import RiraFhirSettings

_APPOINTMENT_STATUS_MAP = {
    "pending": "proposed",
    "returned-to-requester": "proposed",
    "booked": "booked",
    "attended": "fulfilled",
}


def montar_bundle(
    dados: RiraDocumentData,
    settings: RiraFhirSettings,
    composition_status: str,
) -> dict:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    appointment_status = _APPOINTMENT_STATUS_MAP[composition_status]
    id_rnds_anterior = _buscar_id_rnds_anterior(dados.id_local)

    condition = Condition.from_rira(dados, settings, timestamp)
    service_request = ServiceRequest.from_rira(dados, settings, FULLURL_CONDITION, timestamp)
    appointment = Appointment.from_rira(
        dados, settings, appointment_status, FULLURL_SERVICE_REQUEST, FULLURL_CONDITION, timestamp
    )
    composition = Composition.from_rira(
        dados, settings, composition_status, FULLURL_APPOINTMENT, timestamp, id_rnds_anterior
    )
    bundle = Bundle.from_rira(dados, settings, composition, appointment, service_request, condition, timestamp)
    return bundle.model_dump(exclude_none=True)


def dump_bundle_json(dados: RiraDocumentData, composition_status: str) -> str:
    settings = RiraFhirSettings.from_environment()
    return json.dumps(montar_bundle(dados, settings, composition_status), ensure_ascii=False, indent=2)


def extrair_id_rnds(location_header: str) -> str:
    return location_header.rstrip("/").split("/")[-1]


def salvar_envio(id_local: str, id_rnds: str, status: str) -> None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        RNDSDocumentRecord.objects.update_or_create(
            id_local=id_local,
            defaults={"id_rnds": id_rnds, "status": status, "erro": None},
        )
    except Exception:
        pass


def registrar_erro(id_local: str, erro: str) -> None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        RNDSDocumentRecord.objects.update_or_create(
            id_local=id_local,
            defaults={"erro": erro},
        )
    except Exception:
        pass


def _buscar_id_rnds_anterior(id_local: str) -> str | None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        record = RNDSDocumentRecord.objects.filter(id_local=id_local).first()
        return record.id_rnds if record and record.id_rnds else None
    except Exception:
        return None
