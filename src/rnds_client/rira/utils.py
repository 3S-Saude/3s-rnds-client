from __future__ import annotations

from rnds_client.rira.codesystems import CPF_SYSTEM, CNS_SYSTEM


def patient_identifier_system(identificador: str) -> str:
    digits = "".join(c for c in identificador if c.isdigit())
    if len(digits) == 11:
        return CPF_SYSTEM
    return CNS_SYSTEM
