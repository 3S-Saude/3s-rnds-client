from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiraDocumentData:
    id_local: str
    id_paciente: str
    sigtap: str
    cid10: str
    data_solicitacao: str
    cnes_solicitante: str
    modalidade: str
    carater: str
    cnes_regulador: str | None = None
    cnes_executante: str | None = None
    cbo_executante: str | None = None
    data_autorizacao: str | None = None
    data_agendamento: str | None = None
    data_atendimento: str | None = None
