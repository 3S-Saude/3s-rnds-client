from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from rnds_client.rira.codesystems import (
    CNES_SYSTEM,
    MODALIDADE_SYSTEM,
    STATUS_REGULACAO_SYSTEM,
    TIPO_DOCUMENTO_SYSTEM,
)
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta, Period
from rnds_client.rira.utils import patient_identifier_system

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings

_STATUS_RETURNED = "returned-to-requester"


class CompositionEventDetail(BaseModel):
    identifier: Identifier | None = None
    reference: str | None = None


class CompositionEvent(BaseModel):
    code: list[CodeableConcept]
    period: Period
    detail: list[CompositionEventDetail]


class SectionEntry(BaseModel):
    reference: str


class Section(BaseModel):
    entry: list[SectionEntry]


class RelatesToTargetRef(BaseModel):
    reference: str


class RelatesTo(BaseModel):
    code: str
    targetReference: RelatesToTargetRef


class Composition(BaseModel):
    resourceType: str = "Composition"
    meta: Meta
    status: str = "final"
    type: CodeableConcept
    category: list[CodeableConcept]
    subject: IdentifierRef
    date: str
    author: list[IdentifierRef]
    title: str = "Registro de Informações da Regulação Assistencial"
    event: list[CompositionEvent]
    section: list[Section]
    relatesTo: list[RelatesTo] | None = None

    @classmethod
    def from_rira(
        cls,
        dados: RiraDocumentData,
        settings: RiraFhirSettings,
        composition_status: str,
        appointment_ref: str,
        event_ref: str,
        timestamp: str,
        id_rnds_anterior: str | None,
    ) -> Composition:
        end_date = (
            dados.data_atendimento
            or dados.data_agendamento
            or dados.data_autorizacao
            or dados.data_solicitacao
        )
        author_cnes = dados.cnes_regulador or dados.cnes_executante or settings.cnes_autor

        detail: list[CompositionEventDetail] = [
            CompositionEventDetail(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes))
        ]
        if composition_status == _STATUS_RETURNED:
            detail.append(CompositionEventDetail(reference=event_ref))

        relates_to = (
            [RelatesTo(
                code="replaces",
                targetReference=RelatesToTargetRef(reference=f"Composition/{id_rnds_anterior}"),
            )]
            if id_rnds_anterior
            else None
        )

        return cls(
            meta=Meta(profile=[settings.comp_profile]),
            type=CodeableConcept(coding=[Coding(system=TIPO_DOCUMENTO_SYSTEM, code="RA")]),
            category=[
                CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])
            ],
            subject=IdentifierRef(
                identifier=Identifier(
                    system=patient_identifier_system(dados.id_paciente),
                    value=dados.id_paciente,
                )
            ),
            date=timestamp,
            author=[IdentifierRef(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes))],
            event=[
                CompositionEvent(
                    code=[
                        CodeableConcept(
                            coding=[Coding(system=STATUS_REGULACAO_SYSTEM, code=composition_status)]
                        )
                    ],
                    period=Period(start=dados.data_solicitacao, end=end_date),
                    detail=detail,
                )
            ],
            section=[Section(entry=[SectionEntry(reference=appointment_ref)])],
            relatesTo=relates_to,
        )
