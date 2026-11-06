from __future__ import annotations

from rnds_client.base_client import RndsBaseClient
from rnds_client.capabilities import EstablishmentsCapability, PatientsCapability, RiraCapability


class RndsClient:
    def __init__(self, base_client: RndsBaseClient) -> None:
        self._base_client = base_client
        self.pacientes = PatientsCapability(base_client)
        self.estabelecimentos = EstablishmentsCapability(base_client)
        self.rira = RiraCapability(base_client)

    @classmethod
    async def create(cls, *, http_timeout=None, attempts=5, token_cache=None, token_lock=None) -> "RndsClient":
        if http_timeout is None and attempts == 5 and token_cache is None and token_lock is None:
            return cls(base_client=await RndsBaseClient.create())
        return cls(base_client=await RndsBaseClient.create(
            http_timeout=http_timeout, attempts=attempts, token_cache=token_cache, token_lock=token_lock,
        ))

    async def aclose(self) -> None:
        await self._base_client.aclose()

    async def __aenter__(self) -> "RndsClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

