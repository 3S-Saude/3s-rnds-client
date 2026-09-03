from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from httpx import (
    ConnectError,
    ConnectTimeout,
    HTTPStatusError,
    PoolTimeout,
    ReadError,
    ReadTimeout,
    RemoteProtocolError,
    Response,
    TransportError,
    WriteTimeout,
)
from pydantic import ValidationError as PydanticValidationError

from rnds_client.rira.codesystems import FULLURL_APPOINTMENT, FULLURL_CONDITION, FULLURL_SERVICE_REQUEST
from rnds_client.rira.exceptions import (
    ErroRiraRejeitado,
    ErroRiraTransitorio,
    ResultadoRiraIncerto,
    RiraValidationError,
    RndsSubmissionError,
)
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

_STATUS_RETENTAVEIS_4XX = {408, 429}
_TIMEOUT_EXC = (ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout)
_LEITURA_RESPOSTA_EXC = (ReadTimeout, ReadError, RemoteProtocolError)


def montar_bundle(
    dados: RiraDocumentData,
    settings: RiraFhirSettings,
    composition_status: str,
    predecessor_composition_id: str | None = None,
) -> dict:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    appointment_status = _APPOINTMENT_STATUS_MAP[composition_status]

    condition = Condition.from_rira(dados, settings, timestamp)
    service_request = ServiceRequest.from_rira(
        dados, settings, FULLURL_CONDITION, timestamp, composition_status
    )
    appointment = Appointment.from_rira(
        dados, settings, appointment_status, FULLURL_SERVICE_REQUEST, FULLURL_CONDITION, timestamp
    )
    composition = Composition.from_rira(
        dados, settings, composition_status, FULLURL_APPOINTMENT, timestamp, predecessor_composition_id
    )
    bundle = Bundle.from_rira(dados, settings, composition, appointment, service_request, condition, timestamp)
    return bundle.model_dump(exclude_none=True)


def dump_bundle_json(
    dados: RiraDocumentData,
    composition_status: str,
    predecessor_composition_id: str | None = None,
) -> str:
    settings = RiraFhirSettings.from_environment()
    bundle_dict = montar_bundle(dados, settings, composition_status, predecessor_composition_id)
    return json.dumps(bundle_dict, ensure_ascii=False, indent=2)


def extrair_id_rnds(location_header: str) -> str:
    if not location_header:
        raise RndsSubmissionError(
            "Resposta da RNDS nao contem o header 'location' com o ID do documento criado."
        )
    return location_header.rstrip("/").split("/")[-1]


def _referencia_fhir(ref: str) -> tuple[str | None, str | None]:
    partes = [p for p in (ref or "").strip("/").split("/") if p]
    if "_history" in partes:
        partes = partes[: partes.index("_history")]
    if len(partes) >= 2:
        return partes[-2], partes[-1]
    if len(partes) == 1:
        return None, partes[0]
    return None, None


def extrair_ids_resposta(response: Response) -> tuple[str | None, str | None]:
    try:
        corpo: Any = response.json()
    except Exception:
        corpo = None

    if not isinstance(corpo, dict):
        return None, None

    bundle_id = corpo.get("id")
    composition_id = None
    for entry in corpo.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        recurso = entry.get("resource")
        if isinstance(recurso, dict) and recurso.get("resourceType") == "Composition":
            composition_id = recurso.get("id")
        resposta_entry = entry.get("response")
        if isinstance(resposta_entry, dict):
            tipo, ident = _referencia_fhir(resposta_entry.get("location", ""))
            if ident and tipo == "Composition" and not composition_id:
                composition_id = ident
            elif ident and tipo in (None, "Bundle") and not bundle_id:
                bundle_id = ident
    return bundle_id, composition_id


def _retry_after_segundos(response: Response | None) -> int | None:
    if response is None:
        return None
    valor = response.headers.get("retry-after")
    if not valor:
        return None
    if valor.isdigit():
        return int(valor)
    try:
        alvo = parsedate_to_datetime(valor)
        delta = (alvo - datetime.now(tz=alvo.tzinfo)).total_seconds()
        return max(0, int(delta))
    except (TypeError, ValueError):
        return None


def _erro_de_completude(exc: Exception) -> RiraValidationError | None:
    if isinstance(exc, RiraValidationError):
        return exc
    for candidata in (getattr(exc, "__cause__", None), getattr(exc, "__context__", None)):
        if isinstance(candidata, RiraValidationError):
            return candidata
    if isinstance(exc, PydanticValidationError):
        return RiraValidationError(str(exc))
    return None


def classificar_erro_http(exc: Exception, *, apos_post: bool = False) -> Exception:
    completude = _erro_de_completude(exc)
    if completude is not None:
        return ErroRiraRejeitado(str(completude), codigo="completude")

    if isinstance(exc, KeyError):
        return ErroRiraRejeitado(f"Configuração RIRA ausente: {exc}", codigo="configuracao")

    if isinstance(exc, HTTPStatusError):
        status = exc.response.status_code
        if status in _STATUS_RETENTAVEIS_4XX or 500 <= status < 600:
            return ErroRiraTransitorio(
                str(exc), codigo=f"http_{status}", retry_after=_retry_after_segundos(exc.response)
            )
        return ErroRiraRejeitado(str(exc), codigo=f"http_{status}", http_status=status)

    if apos_post and isinstance(exc, _LEITURA_RESPOSTA_EXC):
        return ResultadoRiraIncerto(str(exc), codigo="resposta_perdida")

    if isinstance(exc, _TIMEOUT_EXC):
        return ErroRiraTransitorio(str(exc), codigo="timeout")

    if isinstance(exc, (ConnectError, TransportError, RemoteProtocolError)):
        return ErroRiraTransitorio(str(exc), codigo="conexao")

    return ErroRiraRejeitado(str(exc), codigo="desconhecido")
