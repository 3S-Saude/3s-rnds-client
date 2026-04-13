from __future__ import annotations

from rnds_client.base_client import RndsBaseClient


class EstablishmentsCapability:
    def __init__(self, client: RndsBaseClient) -> None:
        self._client = client

