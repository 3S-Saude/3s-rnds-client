from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RiraFhirSettings:
    naming_system_id: str
    cnes_autor: str
    comp_profile: str
    sr_profile: str
    app_profile: str
    cond_profile: str

    @classmethod
    def from_environment(cls) -> "RiraFhirSettings":
        return cls(
            naming_system_id=os.environ["RIRA_NAMING_SYSTEM_ID"],
            cnes_autor=os.environ["RIRA_CNES_AUTOR"],
            comp_profile=os.environ["RIRA_COMP_PROFILE"],
            sr_profile=os.environ["RIRA_SR_PROFILE"],
            app_profile=os.environ["RIRA_APP_PROFILE"],
            cond_profile=os.environ["RIRA_COND_PROFILE"],
        )

    @property
    def bundle_id_system(self) -> str:
        return f"http://www.saude.gov.br/fhir/r4/NamingSystem/BRRNDS-{self.naming_system_id}"
