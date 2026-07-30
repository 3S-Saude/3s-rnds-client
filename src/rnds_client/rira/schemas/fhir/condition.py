from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from rnds_client.rira.codesystems import CID10_SYSTEM, CONDITION_CATEGORY_SYSTEM, CONDITION_CLINICAL_STATUS_SYSTEM, INDIVIDUO_SYSTEM
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings


class Note(BaseModel):
    text: str


class Condition(BaseModel):
    resourceType: str = "Condition"
    meta: Meta
    clinicalStatus: CodeableConcept
    category: list[CodeableConcept]
    code: CodeableConcept
    subject: IdentifierRef
    note: list[Note]

    @classmethod
    def from_rira(cls, dados: RiraDocumentData, settings: RiraFhirSettings, timestamp: str) -> Condition:
        return cls(
            meta=Meta(lastUpdated=timestamp, profile=[settings.cond_profile]),
            clinicalStatus=CodeableConcept(
                coding=[Coding(system=CONDITION_CLINICAL_STATUS_SYSTEM, code="active")]
            ),
            category=[
                CodeableConcept(
                    coding=[Coding(system=CONDITION_CATEGORY_SYSTEM, code="01", display="Principal")]
                )
            ],
            code=CodeableConcept(coding=[Coding(system=CID10_SYSTEM, code=dados.cid10)]),
            subject=IdentifierRef(
                identifier=Identifier(system=INDIVIDUO_SYSTEM, value=dados.id_paciente)
            ),
            note=[Note(text="Sem observações")],
        )
