from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from rnds_client.rira.codesystems import (
    FULLURL_APPOINTMENT,
    FULLURL_COMPOSITION,
    FULLURL_CONDITION,
    FULLURL_SERVICE_REQUEST,
)

if TYPE_CHECKING:
    from rnds_client.rira.schemas.rira_document import RiraDocumentData
    from rnds_client.rira.settings import RiraFhirSettings
    from rnds_client.rira.schemas.fhir.composition import Composition
    from rnds_client.rira.schemas.fhir.appointment import Appointment
    from rnds_client.rira.schemas.fhir.service_request import ServiceRequest
    from rnds_client.rira.schemas.fhir.condition import Condition


class BundleIdentifier(BaseModel):
    system: str
    value: str


class BundleEntry(BaseModel):
    fullUrl: str
    resource: dict[str, Any]


class Bundle(BaseModel):
    resourceType: str = "Bundle"
    identifier: BundleIdentifier
    type: str = "document"
    timestamp: str
    entry: list[BundleEntry]

    @classmethod
    def from_rira(
        cls,
        dados: RiraDocumentData,
        settings: RiraFhirSettings,
        composition: Composition,
        appointment: Appointment,
        service_request: ServiceRequest,
        condition: Condition,
        timestamp: str,
    ) -> Bundle:
        return cls(
            identifier=BundleIdentifier(system=settings.bundle_id_system, value=dados.id_local),
            timestamp=timestamp,
            entry=[
                BundleEntry(
                    fullUrl=FULLURL_COMPOSITION,
                    resource=composition.model_dump(exclude_none=True),
                ),
                BundleEntry(
                    fullUrl=FULLURL_APPOINTMENT,
                    resource=appointment.model_dump(exclude_none=True),
                ),
                BundleEntry(
                    fullUrl=FULLURL_SERVICE_REQUEST,
                    resource=service_request.model_dump(exclude_none=True),
                ),
                BundleEntry(
                    fullUrl=FULLURL_CONDITION,
                    resource=condition.model_dump(exclude_none=True),
                ),
            ],
        )
