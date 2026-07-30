from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from rnds_client.rira.codesystems import (
    APPOINTMENT_TYPE_SYSTEM,
    CBO_SYSTEM,
    MODALIDADE_SYSTEM,
    SIGTAP_SYSTEM,
    TIPO_PARTICIPANTE_SYSTEM,
)
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta
from rnds_client.rira.utils import patient_identifier_system

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings


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

    @classmethod
    def from_rira(
        cls,
        dados: RiraDocumentData,
        settings: RiraFhirSettings,
        appointment_status: str,
        service_request_ref: str,
        condition_ref: str,
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
            meta=Meta(profile=[settings.app_profile]),
            status=appointment_status,
            serviceCategory=[
                CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])
            ],
            serviceType=[
                CodeableConcept(coding=[Coding(system=SIGTAP_SYSTEM, code=dados.sigtap)])
            ],
            appointmentType=CodeableConcept(
                coding=[Coding(system=APPOINTMENT_TYPE_SYSTEM, code="ROUTINE")]
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
                        identifier=Identifier(
                            system=patient_identifier_system(dados.id_paciente),
                            value=dados.id_paciente,
                        )
                    ),
                    status="accepted",
                )
            ],
        )
