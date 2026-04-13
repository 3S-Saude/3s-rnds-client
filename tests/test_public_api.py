import unittest

from rnds_client import AuthMethod, RndsClient, RndsSettings


class PublicApiTests(unittest.TestCase):
    def test_public_symbols_are_importable(self) -> None:
        self.assertIsNotNone(RndsClient)
        self.assertIsNotNone(RndsSettings)
        self.assertEqual(AuthMethod.API.value, "API")

