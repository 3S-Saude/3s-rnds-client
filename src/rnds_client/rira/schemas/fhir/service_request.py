from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from rnds_client.rira.codesystems import CBO_SYSTEM, CNES_SYSTEM, MODALIDADE_SYSTEM, SIGTAP_SYSTEM
from rnds_client.rira.exceptions import RiraValidationError
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta
from rnds_client.rira.utils import patient_identifier_system

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
    requester: IdentifierRef
    reasonReference: list[dict]
    performerType: CodeableConcept | None = None  # CBO — obrigatório para grupos 03/04
    performer: list[IdentifierRef] | None = None  # CNES executante

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
        return cls(
            meta=Meta(profile=[settings.sr_profile]),
            category=[CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])],
            priority=dados.carater,
            code=CodeableConcept(coding=[Coding(system=SIGTAP_SYSTEM, code=dados.sigtap)]),
            subject=IdentifierRef(
                identifier=Identifier(
                    system=patient_identifier_system(dados.id_paciente),
                    value=dados.id_paciente,
                )
            ),
            authoredOn=dados.data_solicitacao,
            requester=IdentifierRef(
                identifier=Identifier(system=CNES_SYSTEM, value=dados.cnes_solicitante)
            ),
            reasonReference=[{"reference": condition_ref}],
            performerType=performer_type,
            performer=performer,
        )
