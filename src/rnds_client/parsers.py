from __future__ import annotations

from typing import Any


def format_patient_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        return None

    resource = entries[0].get("resource", {})
    if not isinstance(resource, dict) or not resource:
        return None

    identifiers = resource.get("identifier", [])
    if not isinstance(identifiers, list):
        identifiers = []

    patient_info: dict[str, Any] = {
        "cep": None,
        "cns": _main_cns(identifiers),
        "lista_cns": _all_cns(identifiers),
        "cpf": None,
        "nome": resource.get("name", [{}])[0].get("text"),
        "nome_da_mae": None,
        "bairro": None,
        "numero": None,
        "ibge": None,
        "logradouro": None,
        "complemento": None,
        "data_nascimento": resource.get("birthDate"),
        "raca_cor": None,
        "falecido": resource.get("deceasedBoolean", False),
        "data_falecimento": None,
        "telefone": None,
        "email": None,
    }

    match resource.get("gender"):
        case "male":
            patient_info["sexo"] = "M"
        case "female":
            patient_info["sexo"] = "F"
        case _:
            patient_info["sexo"] = "N"

    for identifier in identifiers:
        if "cpf" in identifier.get("system", ""):
            patient_info["cpf"] = identifier.get("value")
            break

    extensions = resource.get("extension", [])
    if isinstance(extensions, list):
        for extension in extensions:
            extension_url = extension.get("url", "")
            nested_extensions = extension.get("extension", [])

            if "rnds-race" in extension_url and nested_extensions:
                patient_info["raca_cor"] = (
                    nested_extensions[0]
                    .get("valueCodeableConcept", {})
                    .get("coding", [{}])[0]
                    .get("code")
                )

            if "rnds-parent" in extension_url and nested_extensions:
                parent_code = (
                    nested_extensions[0]
                    .get("valueCodeableConcept", {})
                    .get("coding", [{}])[0]
                    .get("code")
                )
                if parent_code == "MTH" and len(nested_extensions) > 1:
                    patient_info["nome_da_mae"] = nested_extensions[1].get("valueHumanName", {}).get("text")

    telecoms = resource.get("telecom", [])
    if isinstance(telecoms, list):
        for telecom in telecoms:
            system = telecom.get("system")
            value = telecom.get("value")

            if not value:
                continue

            if system == "phone" and patient_info["telefone"] is None:
                patient_info["telefone"] = value

            if system == "email" and patient_info["email"] is None:
                patient_info["email"] = value

            if patient_info["telefone"] is not None and patient_info["email"] is not None:
                break

    addresses = resource.get("address", [])
    if isinstance(addresses, list) and addresses:
        address = addresses[0]
        patient_info["cep"] = address.get("postalCode")
        patient_info["bairro"] = address.get("district")
        patient_info["complemento"] = address.get("text")

        city = address.get("_city", {})
        if isinstance(city, dict):
            patient_info["ibge"] = city.get("extension", [{}])[0].get("valueString")

        address_lines = address.get("line", [])
        if isinstance(address_lines, list):
            if len(address_lines) > 0:
                patient_info["logradouro"] = address_lines[0]
            if len(address_lines) > 1:
                patient_info["numero"] = address_lines[1]
            if len(address_lines) > 2 and not patient_info["complemento"]:
                patient_info["complemento"] = address_lines[2]

    return patient_info


def _main_cns(identifiers: list[dict[str, Any]]) -> str | None:
    for identifier in identifiers:
        if identifier.get("use") == "official":
            return identifier.get("value")
    return identifiers[0].get("value") if identifiers else None


def _all_cns(identifiers: list[dict[str, Any]]) -> list[str]:
    return [
        identifier.get("value")
        for identifier in identifiers
        if "cns" in identifier.get("system", "") and identifier.get("value") is not None
    ]

