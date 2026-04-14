import unittest

from rnds_client.parsers import format_organization_payload, format_patient_payload


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


class OrganizationParserTests(unittest.TestCase):
    def test_format_organization_payload_maps_main_fields(self) -> None:
        payload = {
            "resourceType": "Organization",
            "active": True,
            "name": "SECRETARIA DE ESTADO DE SAUDE DE MATO GROSSO",
            "type": [
                {
                    "coding": [
                        {
                            "display": "CENTRAL DE GESTAO EM SAUDE",
                        }
                    ]
                }
            ],
            "telecom": [
                {"system": "phone", "value": "6536135300"},
                {"system": "email", "value": "gbses@ses.mt.gov.br"},
            ],
            "address": [
                {
                    "line": [
                        "RUA JULIO DOMINGOS DE CAMPOS",
                        "S/N",
                        "BLOCO 05",
                    ],
                    "_city": {
                        "extension": [
                            {
                                "valueString": "510340",
                            }
                        ]
                    },
                    "district": "CPA",
                    "postalCode": "78049902",
                }
            ],
        }

        result = format_organization_payload(payload)

        self.assertEqual(
            result,
            {
                "nome": "SECRETARIA DE ESTADO DE SAUDE DE MATO GROSSO",
                "telefone": "6536135300",
                "email": "gbses@ses.mt.gov.br",
                "ativo": True,
                "tipo": "CENTRAL DE GESTAO EM SAUDE",
                "ibge": "510340",
                "logradouro": "RUA JULIO DOMINGOS DE CAMPOS",
                "bairro": "CPA",
                "numero": "S/N",
                "cep": "78049902",
            },
        )
