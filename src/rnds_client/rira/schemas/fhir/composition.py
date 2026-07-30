from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from rnds_client.rira.codesystems import (
    CNES_SYSTEM,
    FULLURL_APPOINTMENT,
    FULLURL_SERVICE_REQUEST,
    INDIVIDUO_SYSTEM,
    MODALIDADE_SYSTEM,
    STATUS_REGULACAO_SYSTEM,
    TIPO_DOCUMENTO_SYSTEM,
)
from rnds_client.rira.schemas.fhir.primitives import Coding, CodeableConcept, Identifier, IdentifierRef, Meta, Period

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings

_STATUS_VERSION = "20230801"


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

        if composition_status == "pending":
            detail: list[CompositionEventDetail] = [
                CompositionEventDetail(reference=FULLURL_SERVICE_REQUEST),
                CompositionEventDetail(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes)),
            ]
        elif composition_status in ("booked", "attended"):
            detail = [
                CompositionEventDetail(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes)),
                CompositionEventDetail(reference=FULLURL_APPOINTMENT),
            ]
        else:  # returned-to-requester
            detail = [
                CompositionEventDetail(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes)),
            ]

        relates_to = (
            [RelatesTo(
                code="replaces",
                targetReference=RelatesToTargetRef(reference=f"Composition/{id_rnds_anterior}"),
            )]
            if id_rnds_anterior
            else None
        )

        return cls(
            meta=Meta(lastUpdated=timestamp, profile=[settings.comp_profile]),
            type=CodeableConcept(coding=[Coding(system=TIPO_DOCUMENTO_SYSTEM, code="RA")]),
            category=[
                CodeableConcept(coding=[Coding(system=MODALIDADE_SYSTEM, code=dados.modalidade)])
            ],
            subject=IdentifierRef(
                identifier=Identifier(system=INDIVIDUO_SYSTEM, value=dados.id_paciente)
            ),
            date=timestamp,
            author=[IdentifierRef(identifier=Identifier(system=CNES_SYSTEM, value=author_cnes))],
            event=[
                CompositionEvent(
                    code=[
                        CodeableConcept(
                            coding=[Coding(
                                system=STATUS_REGULACAO_SYSTEM,
                                version=_STATUS_VERSION,
                                code=composition_status,
                            )]
                        )
                    ],
                    period=Period(start=dados.data_solicitacao, end=end_date),
                    detail=detail,
                )
            ],
            section=[Section(entry=[SectionEntry(reference=appointment_ref)])],
            relatesTo=relates_to,
        )
