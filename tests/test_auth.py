import unittest
from unittest.mock import patch

from httpx import AsyncClient, Timeout

from rnds_client.auth import _HTTP_TIMEOUT_SECONDS, build_http_client
from rnds_client.settings import AuthMethod, CertificateFiles, RndsSettings


def _api_settings() -> RndsSettings:
    return RndsSettings(
        auth_method=AuthMethod.API,
        auth_token_url="https://auth.example/token",
        auth_login_url="https://auth.example/login",
        service_url="https://service.example/api",
    )


def _cert_settings() -> RndsSettings:
    return RndsSettings(
        auth_method=AuthMethod.CERT,
        auth_token_url="https://auth.example/token",
        service_url="https://service.example/api",
        certificate_files=CertificateFiles(certificate="/tmp/cert.pem", key="/tmp/key.pem"),
    )


class BuildHttpClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_client_uses_two_minute_timeout_for_all_network_phases(self) -> None:
        client = build_http_client(_api_settings())
        self.addAsyncCleanup(client.aclose)

        self._assert_all_timeouts_are_two_minutes(client)

    async def test_cert_client_uses_two_minute_timeout_for_all_network_phases(self) -> None:
        with patch("rnds_client.auth.AsyncClient", autospec=True) as async_client:
            build_http_client(_cert_settings())

        timeout = async_client.call_args.kwargs["timeout"]
        self._assert_all_timeouts_are_two_minutes(timeout)

    def _assert_all_timeouts_are_two_minutes(self, timeout: Timeout | AsyncClient) -> None:
        if isinstance(timeout, AsyncClient):
            timeout = timeout.timeout
        self.assertEqual(timeout.connect, _HTTP_TIMEOUT_SECONDS)
        self.assertEqual(timeout.read, _HTTP_TIMEOUT_SECONDS)
        self.assertEqual(timeout.write, _HTTP_TIMEOUT_SECONDS)
        self.assertEqual(timeout.pool, _HTTP_TIMEOUT_SECONDS)
