from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoEnvioRira:

    http_status: int
    location_rnds: str | None = None
    id_rnds_bundle: str | None = None
    id_rnds_composition: str | None = None
    codigo_erro: str | None = None
    mensagem_sanitizada: str | None = None
