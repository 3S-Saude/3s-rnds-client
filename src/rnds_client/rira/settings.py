from __future__ import annotations

import os
from dataclasses import dataclass


RIRA_COMP_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRRegulacaoAssistencial"
RIRA_SR_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRRequisicaoRegulacaoAssistencial"
RIRA_APP_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRAgendamentoRegulacaoAssistencial"
RIRA_COND_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRCID10Avaliado-1.0"


@dataclass
class RiraFhirSettings:
    naming_system_id: str
    comp_profile: str = RIRA_COMP_PROFILE
    sr_profile: str = RIRA_SR_PROFILE
    app_profile: str = RIRA_APP_PROFILE
    cond_profile: str = RIRA_COND_PROFILE
    bundle_id_system_override: str | None = None

    @classmethod
    def from_environment(
        cls, *, bundle_id_system_override: str | None = None
    ) -> "RiraFhirSettings":
        exige_naming = bundle_id_system_override is None
        return cls(
            naming_system_id=(
                os.environ["RIRA_NAMING_SYSTEM_ID"]
                if exige_naming
                else os.environ.get("RIRA_NAMING_SYSTEM_ID", "")
            ),
            bundle_id_system_override=bundle_id_system_override,
        )

    @property
    def bundle_id_system(self) -> str:
        if self.bundle_id_system_override:
            return self.bundle_id_system_override
        return f"http://www.saude.gov.br/fhir/r4/NamingSystem/BRRNDS-{self.naming_system_id}"
