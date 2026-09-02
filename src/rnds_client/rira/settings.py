from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RiraFhirSettings:
    naming_system_id: str
    comp_profile: str
    sr_profile: str
    app_profile: str
    cond_profile: str
    bundle_id_system_override: str | None = None

    @classmethod
    def from_environment(cls) -> "RiraFhirSettings":
        return cls(
            naming_system_id=os.environ["RIRA_NAMING_SYSTEM_ID"],
            comp_profile=os.environ["RIRA_COMP_PROFILE"],
            sr_profile=os.environ["RIRA_SR_PROFILE"],
            app_profile=os.environ["RIRA_APP_PROFILE"],
            cond_profile=os.environ["RIRA_COND_PROFILE"],
        )

    @property
    def bundle_id_system(self) -> str:
        if self.bundle_id_system_override:
            return self.bundle_id_system_override
        return f"http://www.saude.gov.br/fhir/r4/NamingSystem/BRRNDS-{self.naming_system_id}"
