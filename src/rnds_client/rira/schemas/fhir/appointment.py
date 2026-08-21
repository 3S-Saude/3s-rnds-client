from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from rnds_client.rira.codesystems import (
    APPOINTMENT_TYPE_SYSTEM,
    CBO_SYSTEM,
    INDIVIDUO_SYSTEM,
    MODALIDADE_SYSTEM,
    SIGTAP_SYSTEM,
    TIPO_PARTICIPANTE_SYSTEM,
)
from rnds_client.rira.exceptions import RiraValidationError
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings

_STATUS_DISPENSA_START_END = {"proposed", "cancelled", "waitlist"}


class AppointmentParticipant(BaseModel):
    type: list[CodeableConcept]
    actor: IdentifierRef
    status: str


class Appointment(BaseModel):
    resourceType: str = "Appointment"
    meta: Meta
    status: str
    serviceCategory: list[CodeableConcept]
    serviceType: list[CodeableConcept]
    appointmentType: CodeableConcept
    specialty: list[CodeableConcept] | None = None
    reasonReference: list[dict]
    start: str | None = None
    end: str | None = None
    created: str
    basedOn: list[dict]
    participant: list[AppointmentParticipant]

    @model_validator(mode="after")
    def datas_obrigatorias_para_status_confirmado(self) -> Appointment:
        if self.status not in _STATUS_DISPENSA_START_END and (self.start is None or self.end is None):
            raise RiraValidationError(
                f"status '{self.status}' exige start e end (invariante FHIR Appointment). "
                "Preencha data_agendamento ou data_autorizacao em RiraDocumentData."
            )
        return self

    @classmethod
    def from_rira(
        cls,
        dados: RiraDocumentData,
        settings: RiraFhirSettings,
        appointment_status: str,
        service_request_ref: str,
        condition_ref: str,
        timestamp: str,
    ) -> Appointment:
        end_date = (
            dados.data_atendimento
            or dados.data_agendamento
            or dados.data_autorizacao
            or dados.data_solicitacao
        )
        start = dados.data_agendamento or dados.data_autorizacao
        specialty = (
            [CodeableConcept(coding=[Coding(system=CBO_SYSTEM, code=dados.cbo_executante)])]
            if dados.cbo_executante
            else None
        )
        return cls(
            meta=Meta(lastUpdated=timestamp, profile=[settings.app_profile]),
            status=appointment_status,
            serviceCategory=[
                CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])
            ],
            serviceType=[
                CodeableConcept(coding=[Coding(system=SIGTAP_SYSTEM, code=dados.sigtap)])
            ],
            appointmentType=CodeableConcept(
                coding=[Coding(system=APPOINTMENT_TYPE_SYSTEM, code=dados.carater)]
            ),
            specialty=specialty,
            reasonReference=[{"reference": condition_ref}],
            start=start,
            end=end_date if start else None,
            created=dados.data_solicitacao,
            basedOn=[{"reference": service_request_ref}],
            participant=[
                AppointmentParticipant(
                    type=[
                        CodeableConcept(coding=[Coding(system=TIPO_PARTICIPANTE_SYSTEM, code="PCT")])
                    ],
                    actor=IdentifierRef(
                        identifier=Identifier(system=INDIVIDUO_SYSTEM, value=dados.id_paciente)
                    ),
                    status="accepted",
                )
            ],
        )
