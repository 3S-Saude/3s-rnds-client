from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from rnds_client.rira.codesystems import FULLURL_APPOINTMENT, FULLURL_CONDITION, FULLURL_SERVICE_REQUEST
from rnds_client.rira.exceptions import RndsSubmissionError
from rnds_client.rira.schemas.fhir.appointment import Appointment
from rnds_client.rira.schemas.fhir.bundle import Bundle
from rnds_client.rira.schemas.fhir.composition import Composition
from rnds_client.rira.schemas.fhir.condition import Condition
from rnds_client.rira.schemas.fhir.service_request import ServiceRequest
from rnds_client.rira.schemas.rira_document import RiraDocumentData
from rnds_client.rira.settings import RiraFhirSettings

logger = logging.getLogger(__name__)

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
    id_rnds_anterior: str | None = None,
) -> dict:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    appointment_status = _APPOINTMENT_STATUS_MAP[composition_status]

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


def dump_bundle_json(
    dados: RiraDocumentData,
    composition_status: str,
    id_rnds_anterior: str | None = None,
) -> str:
    settings = RiraFhirSettings.from_environment()
    bundle_dict = montar_bundle(dados, settings, composition_status, id_rnds_anterior)
    return json.dumps(bundle_dict, ensure_ascii=False, indent=2)


def extrair_id_rnds(location_header: str) -> str:
    if not location_header:
        raise RndsSubmissionError(
            "Resposta da RNDS nao contem o header 'location' com o ID do documento criado."
        )
    return location_header.rstrip("/").split("/")[-1]


async def salvar_envio(id_local: str, id_rnds: str, status: str) -> None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        await RNDSDocumentRecord.objects.aupdate_or_create(
            id_local=id_local,
            defaults={"id_rnds": id_rnds, "status": status, "erro": None},
        )
    except Exception:
        logger.exception("Falha ao salvar o envio RNDS no banco local (id_local=%s).", id_local)


async def registrar_erro(id_local: str, erro: str) -> None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        await RNDSDocumentRecord.objects.aupdate_or_create(
            id_local=id_local,
            defaults={"erro": erro},
        )
    except Exception:
        logger.exception("Falha ao registrar erro do envio RNDS no banco local (id_local=%s).", id_local)


async def buscar_id_rnds_anterior(id_local: str) -> str | None:
    try:
        from rnds_client.rira.models.rnds_record import RNDSDocumentRecord
        record = await RNDSDocumentRecord.objects.filter(id_local=id_local).afirst()
        return record.id_rnds if record and record.id_rnds else None
    except Exception:
        logger.exception("Falha ao buscar o id_rnds anterior no banco local (id_local=%s).", id_local)
        return None
