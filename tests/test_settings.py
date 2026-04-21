import os
import unittest
from unittest.mock import patch

from rnds_client.exceptions import RndsConfigurationError
from rnds_client.settings import AuthMethod, RndsSettings


class SettingsTests(unittest.TestCase):
    def test_auth_method_defaults_to_api_when_credentials_exist(self) -> None:
        with patch.dict(os.environ, {"RNDS_USER": "user", "RNDS_PASSWORD": "secret"}, clear=True):
            self.assertEqual(AuthMethod.from_environment(), AuthMethod.API)

    def test_cert_settings_require_cert_and_key(self) -> None:
        env = {
            "RNDS_AUTH_METHOD": "CERT",
            "RNDS_API_URL": "https://service.example",
            "RNDS_AUTH_TOKEN_URL": "https://auth.example",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RndsConfigurationError):
                RndsSettings.from_environment()

    def test_api_settings_accept_legacy_cns_sec_saude_variable(self) -> None:
        env = {
            "RNDS_AUTH_METHOD": "API",
            "RNDS_API_URL": "https://service.example",
            "RNDS_AUTH_LOGIN_URL": "https://auth.example/login",
            "RNDS_AUTH_TOKEN_URL": "https://auth.example/token",
            "RNDS_USER": "user",
            "RNDS_PASSWORD": "secret",
            "CNS_SEC_SAUDE": "Bearer gestor-legado",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = RndsSettings.from_environment()

        self.assertEqual(settings.cns_authorization, "Bearer gestor-legado")

    def test_rnds_cns_gestor_takes_precedence_over_legacy_variable(self) -> None:
        env = {
            "RNDS_AUTH_METHOD": "API",
            "RNDS_API_URL": "https://service.example",
            "RNDS_AUTH_LOGIN_URL": "https://auth.example/login",
            "RNDS_AUTH_TOKEN_URL": "https://auth.example/token",
            "RNDS_USER": "user",
            "RNDS_PASSWORD": "secret",
            "RNDS_CNS_GESTOR": "Bearer gestor-atual",
            "CNS_SEC_SAUDE": "Bearer gestor-legado",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = RndsSettings.from_environment()

        self.assertEqual(settings.cns_authorization, "Bearer gestor-atual")
