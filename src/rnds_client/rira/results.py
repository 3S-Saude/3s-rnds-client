from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResultadoEnvioRira:

    http_status: int
    location_rnds: str | None = None
    id_rnds_bundle: str | None = None
    id_rnds_composition: str | None = None
    codigo_erro: str | None = None
    mensagem_sanitizada: str | None = None
    status_rira: str | None = None
    predecessor_composition_id: str | None = None
    dados_clinicos: dict[str, Any] | None = None
