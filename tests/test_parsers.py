import unittest

from rnds_client.parsers import format_patient_payload


class PatientParserTests(unittest.TestCase):
    def test_format_patient_payload_maps_main_fields(self) -> None:
        payload = {
            "entry": [
                {
                    "resource": {
                        "identifier": [
                            {"use": "official", "system": "http://rnds/cns", "value": "111"},
                            {"system": "http://rnds/cpf", "value": "12345678901"},
                        ],
                        "name": [{"text": "Paciente Teste"}],
                        "birthDate": "2001-02-03",
                        "gender": "female",
                        "telecom": [
                            {"system": "phone", "value": "5561999999999"},
                            {"system": "email", "value": "paciente.teste@exemplo.com"},
                        ],
                    }
                }
            ]
        }

        result = format_patient_payload(payload)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["cns"], "111")
        self.assertEqual(result["cpf"], "12345678901")
        self.assertEqual(result["nome"], "Paciente Teste")
        self.assertEqual(result["sexo"], "F")

