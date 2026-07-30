from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from rnds_client.rira.codesystems import CBO_SYSTEM, CNES_SYSTEM, INDIVIDUO_SYSTEM, MODALIDADE_SYSTEM, SIGTAP_SYSTEM
from rnds_client.rira.exceptions import RiraValidationError
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings


class ServiceRequest(BaseModel):
    resourceType: str = "ServiceRequest"
    meta: Meta
    status: str = "active"
    intent: str = "proposal"
    category: list[CodeableConcept]
    priority: str
    code: CodeableConcept
    subject: IdentifierRef
    authoredOn: str
    occurrenceDateTime: str | None = None
    requester: IdentifierRef
    reasonReference: list[dict]
    performerType: CodeableConcept | None = None
    performer: list[IdentifierRef] | None = None

    @model_validator(mode="after")
    def cbo_obrigatorio_grupos_03_04(self) -> ServiceRequest:
        sigtap_grupo = self.code.coding[0].code[:2]
        if sigtap_grupo in ("03", "04") and self.performerType is None:
            raise RiraValidationError(
                f"CBO obrigatório para procedimentos SIGTAP do grupo {sigtap_grupo}. "
                "Preencha cbo_executante em RiraDocumentData."
            )
        return self

    @classmethod
    def from_rira(
        cls,
        dados: RiraDocumentData,
        settings: RiraFhirSettings,
        condition_ref: str,
        timestamp: str,
    ) -> ServiceRequest:
        performer_type = (
            CodeableConcept(coding=[Coding(system=CBO_SYSTEM, code=dados.cbo_executante)])
            if dados.cbo_executante
            else None
        )
        performer = (
            [IdentifierRef(identifier=Identifier(system=CNES_SYSTEM, value=dados.cnes_executante))]
            if dados.cnes_executante
            else None
        )
        occurrence = dados.data_agendamento or dados.data_atendimento
        return cls(
            meta=Meta(lastUpdated=timestamp, profile=[settings.sr_profile]),
            category=[CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])],
            priority=dados.carater,
            code=CodeableConcept(coding=[Coding(system=SIGTAP_SYSTEM, code=dados.sigtap)]),
            subject=IdentifierRef(
                identifier=Identifier(system=INDIVIDUO_SYSTEM, value=dados.id_paciente)
            ),
            authoredOn=dados.data_solicitacao,
            occurrenceDateTime=occurrence,
            requester=IdentifierRef(
                identifier=Identifier(system=CNES_SYSTEM, value=dados.cnes_solicitante)
            ),
            reasonReference=[{"reference": condition_ref}],
            performerType=performer_type,
            performer=performer,
        )
