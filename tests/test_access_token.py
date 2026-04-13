import base64
import json
import time
import unittest

from httpx import Response

from rnds_client.exceptions import RndsAuthenticationError
from rnds_client.tokens import AccessToken


def _jwt_with_exp(expiration: int) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expiration}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"


class AccessTokenTests(unittest.TestCase):
    def test_from_response_extracts_access_token(self) -> None:
        response = Response(200, json={"access_token": "abc"})
        access_token = AccessToken.from_response(response)
        self.assertEqual(access_token.value, "abc")

    def test_cache_timeout_raises_when_token_has_expired(self) -> None:
        token = AccessToken(_jwt_with_exp(int(time.time()) - 5))

        with self.assertRaises(RndsAuthenticationError):
            token.cache_timeout()

