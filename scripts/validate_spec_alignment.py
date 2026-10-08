#!/usr/bin/env python3
"""Validate ODPS docs, examples, and schema alignment."""

from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
INCLUDES = SOURCE / "includes"
EXAMPLES = SOURCE / "examples"
TEMPLATES_DOC = INCLUDES / "_templates.md"
JSON_SCHEMA_PATH = SOURCE / "schema" / "odps.json"
YAML_SCHEMA_PATH = SOURCE / "schema" / "odps.yaml"
CONFORMANCE_FIXTURES = ROOT / "tests" / "fixtures" / "schema-conformance"

IGNORED_DYNAMIC_KEYS = {
    "$ref",
    "en",
    "default",
    "premium",
    "gold",
    "dataonly",
    "API",
    "Agent",
    "agent",
}

COMPONENT_ROOTS = {
    "contract": ("product", "contract"),
    "details": ("product", "details"),
    "pricingPlans": ("product", "pricingPlans"),
    "SLA": ("product", "SLA"),
    "dataQuality": ("product", "dataQuality"),
    "dataAccess": ("product", "dataAccess"),
    "paymentGateways": ("product", "paymentGateways"),
    "license": ("product", "license"),
    "dataHolder": ("product", "dataHolder"),
}

FORBIDDEN_TEXT_PATTERNS = {
    "legacy outputPorttype spelling": r"\boutputPorttype\b",
    "legacy dataHolder businessId spelling": r"\bbusinessId\b",
    "legacy displayTitle spelling": r"\bdisplayTitle\b",
    "lowercase recurring pricing unit": r"\bunit:\s+recurring\b",
    "short SLA reference path": r"#/product/SLA/(?:default|premium|gold)\b",
    "short dataQuality reference path": r"#/product/dataQuality/(?:default|premium)\b",
}


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("uri")
def is_valid_uri(value: object) -> bool:
    """Validate the URI format even when jsonschema has no optional URI dependency."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]*", value):
        return False
    return is_valid_uri_reference(value)


@FORMAT_CHECKER.checks("uri-reference")
def is_valid_uri_reference(value: object) -> bool:
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f\x7f]", value):
        return False
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.hostname
    except ValueError:
        return False
    return True


@dataclass
class Failure:
    check: str
    location: str
    message: str

    def render(self) -> str:
        return f"[{self.check}] {self.location}: {self.message}"


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(read_text(path))


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="ignore")


def yaml_blocks(path: Path) -> list[tuple[int, str]]:
    text = read_text(path)
    pattern = re.compile(r"```(?:ya?ml)\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
    return [(index, match.group(1)) for index, match in enumerate(pattern.finditer(text), 1)]


def is_current_document(value: Any) -> bool:
    if not isinstance(value, dict) or "product" not in value:
        return False
    schema = str(value.get("schema", ""))
    return "v4.2/schema/odps" in schema


def has_template_placeholders(value: Any) -> bool:
    return isinstance(value, str) and "{{" in value and "}}" in value


def contains_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if has_template_placeholders(value):
        return True
    if isinstance(value, str) and "selected dimension" in value:
        return True
    if isinstance(value, dict):
        return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(child) for child in value)
    return False


def is_ref_only(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"$ref"}


def is_ref_map(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(is_ref_only(child) for child in value.values())


def should_schema_validate(value: Any) -> bool:
    return not contains_placeholder(value) and not is_ref_only(value) and not is_ref_map(value)


def is_complete_current_document(value: Any) -> bool:
    return (
        is_current_document(value)
        and isinstance(value.get("product"), dict)
        and "details" in value["product"]
    )


def pointer(schema: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any] | None:
    current: Any = schema
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get("properties", {}).get(part)
        if isinstance(current, dict) and "$ref" in current:
            current = resolve_ref(schema, current["$ref"])
    return current if isinstance(current, dict) else None


def resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"external $ref not supported in validation script: {ref}")
    current: Any = schema
    for part in ref[2:].split("/"):
        current = current[part]
    return current


def validate_instance(
    failures: list[Failure],
    check: str,
    location: str,
    instance: Any,
    schema: dict[str, Any],
) -> None:
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    for error in errors:
        path = "/" + "/".join(str(part) for part in error.path)
        failures.append(Failure(check, f"{location}{path}", error.message))


def standalone_subschema(root_schema: dict[str, Any], subschema: dict[str, Any]) -> dict[str, Any]:
    result = dict(subschema)
    if "$schema" in root_schema:
        result.setdefault("$schema", root_schema["$schema"])
    if "$defs" in root_schema:
        result.setdefault("$defs", root_schema["$defs"])
    return result


def validate_markdown_yaml_examples(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    files = sorted(INCLUDES.glob("*.md")) + [SOURCE / "index.html.md"]
    for path in files:
        for index, block in yaml_blocks(path):
            location = f"{path.relative_to(ROOT)} fenced yaml block #{index}"
            try:
                parsed = yaml.safe_load(block)
            except Exception as exc:  # noqa: BLE001 - report parser's exact message
                failures.append(Failure("markdown-yaml-parse", location, str(exc).splitlines()[0]))
                continue

            if parsed is None:
                failures.append(Failure("markdown-yaml-parse", location, "empty YAML block"))
                continue

            if is_complete_current_document(parsed) and should_schema_validate(parsed):
                validate_instance(failures, "markdown-v42-json-schema", location, parsed, json_schema)
                validate_instance(failures, "markdown-v42-yaml-schema", location, parsed, yaml_schema)
                validate_internal_refs(failures, "markdown-ref-resolution", location, parsed)
                continue

            if isinstance(parsed, dict) and len(parsed) == 1:
                root_key = next(iter(parsed))
                if root_key in COMPONENT_ROOTS and should_schema_validate(parsed[root_key]):
                    json_subschema = pointer(json_schema, COMPONENT_ROOTS[root_key])
                    yaml_subschema = pointer(yaml_schema, COMPONENT_ROOTS[root_key])
                    if json_subschema:
                        validate_instance(
                            failures,
                            "component-json-schema",
                            location,
                            parsed[root_key],
                            standalone_subschema(json_schema, json_subschema),
                        )
                    if yaml_subschema:
                        validate_instance(
                            failures,
                            "component-yaml-schema",
                            location,
                            parsed[root_key],
                            standalone_subschema(yaml_schema, yaml_subschema),
                        )


def validate_standalone_yaml_examples(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    for path in sorted(EXAMPLES.rglob("*.yml")):
        location = str(path.relative_to(ROOT))
        try:
            parsed = load_yaml(path)
        except Exception as exc:  # noqa: BLE001 - report parser's exact message
            failures.append(Failure("example-yaml-parse", location, str(exc).splitlines()[0]))
            continue

        if is_complete_current_document(parsed) and should_schema_validate(parsed):
            validate_instance(failures, "example-v42-json-schema", location, parsed, json_schema)
            validate_instance(failures, "example-v42-yaml-schema", location, parsed, yaml_schema)
            validate_internal_refs(failures, "example-ref-resolution", location, parsed)
            continue

        if path.name == "contract-profiles-package.yml":
            for schema_name, schema in (("json", json_schema), ("yaml", yaml_schema)):
                collection = resolve_ref(schema, "#/$defs/ContractProfileCollection")
                validate_instance(
                    failures,
                    f"contract-package-{schema_name}-schema",
                    location,
                    parsed,
                    standalone_subschema(schema, collection),
                )


def template_links() -> list[Path]:
    text = read_text(TEMPLATES_DOC)
    links = re.findall(r"\]\((examples/Templates/[^)]+\.yml)\)", text)
    return [SOURCE / link for link in links]


def materialize_placeholder(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: materialize_placeholder(child) for key, child in value.items()}
    if isinstance(value, list):
        return [materialize_placeholder(child) for child in value]
    if not has_template_placeholders(value):
        return value

    match = re.fullmatch(r"\{\{([^}]+)\}\}", value.strip())
    if not match:
        return value

    token = match.group(1).strip()
    if token.startswith("enum:"):
        return token.removeprefix("enum:").split("|")[0].strip()
    if token == "integer":
        return 1
    if token == "boolean":
        return True
    if token == "number or string":
        return "1"
    if token == "string: email":
        return "contact@example.org"
    if token == "string: url":
        return "https://example.org/resource"
    if token == "string: semver":
        return "1.0.0"
    if token == "string: ISO 4217 currency code or crypto ticker":
        return "USD"
    if token == "date: YYYY-MM-DD":
        return "2026-01-01"
    if token == "object":
        return {}
    if token == "string":
        return "Example value"
    return value


def validate_template_family(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    linked = template_links()
    if not linked:
        failures.append(Failure("template-family-links", str(TEMPLATES_DOC.relative_to(ROOT)), "no template links found"))
        return

    for path in linked:
        location = str(path.relative_to(ROOT))
        if not path.exists():
            failures.append(Failure("template-family-links", location, "linked template does not exist"))
            continue
        try:
            parsed = load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            failures.append(Failure("template-family-parse", location, str(exc).splitlines()[0]))
            continue
        materialized = materialize_placeholder(parsed)
        if contains_placeholder(materialized):
            failures.append(
                Failure("template-family-placeholders", location, "unresolved placeholder remains after materialization")
            )
            continue
        if not is_complete_current_document(materialized):
            failures.append(Failure("template-family-document", location, "template does not materialize to a v4.2 document"))
            continue
        validate_instance(failures, "template-family-json-schema", location, materialized, json_schema)
        validate_instance(failures, "template-family-yaml-schema", location, materialized, yaml_schema)


def collect_keys(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in IGNORED_DYNAMIC_KEYS:
                keys.add(str(key))
            collect_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            collect_keys(child, keys)


def validate_hello_world_text_alignment(failures: list[Failure]) -> None:
    path = INCLUDES / "_helloworld.md"
    blocks = yaml_blocks(path)
    if len(blocks) != 1:
        failures.append(Failure("hello-world", str(path.relative_to(ROOT)), "expected exactly one YAML block"))
        return

    try:
        parsed = yaml.safe_load(blocks[0][1])
    except Exception as exc:  # noqa: BLE001
        failures.append(Failure("hello-world-parse", str(path.relative_to(ROOT)), str(exc).splitlines()[0]))
        return

    keys: set[str] = set()
    collect_keys(parsed, keys)
    spec_text = "\n".join(
        read_text(file)
        for file in sorted(INCLUDES.glob("*.md")) + [SOURCE / "index.html.md"]
        if file.name != "_helloworld.md"
    )
    for key in sorted(keys):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])")
        if not pattern.search(spec_text):
            failures.append(
                Failure(
                    "hello-world-text-alignment",
                    f"{path.relative_to(ROOT)} key {key}",
                    "key is used in hello world but not defined or mentioned in the textual spec",
                )
            )

    for ref in find_refs(parsed):
        if ref.startswith("#/") and not internal_pointer_exists(parsed, ref):
            failures.append(
                Failure(
                    "hello-world-ref-resolution",
                    f"{path.relative_to(ROOT)} {ref}",
                    "internal reference does not resolve in the hello world document",
                )
            )


def find_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                refs.append(child)
            else:
                refs.extend(find_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(find_refs(child))
    return refs


def internal_pointer_exists(document: Any, ref: str) -> bool:
    current = document
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False
    return True


def validate_internal_refs(failures: list[Failure], check: str, location: str, document: Any) -> None:
    for ref in find_refs(document):
        if ref.startswith("#/") and not internal_pointer_exists(document, ref):
            failures.append(Failure(check, f"{location} {ref}", "internal reference does not resolve"))


def expect_schema_result(
    failures: list[Failure],
    check: str,
    location: str,
    instance: Any,
    schemas: tuple[tuple[str, dict[str, Any]], ...],
    expected_valid: bool,
) -> None:
    outcomes: list[bool] = []
    for schema_name, schema in schemas:
        errors = list(Draft202012Validator(schema, format_checker=FORMAT_CHECKER).iter_errors(instance))
        accepted = not errors
        outcomes.append(accepted)
        if accepted != expected_valid:
            expectation = "valid" if expected_valid else "invalid"
            message = errors[0].message if errors else "fixture was accepted"
            failures.append(Failure(check, f"{location} ({schema_name})", f"expected {expectation}: {message}"))
    if len(set(outcomes)) != 1:
        failures.append(Failure(f"{check}-parity", location, "JSON and YAML schemas disagree"))


def pointer_value(document: Any, ref: str) -> Any | None:
    if not ref.startswith("#/"):
        return None
    current = document
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def contract_target_errors(document: Any) -> list[str]:
    """Return semantic errors for internal Data Access-to-Contract references."""
    product = document.get("product") if isinstance(document, dict) else None
    if not isinstance(product, dict):
        return ["document does not contain a product object"]
    access_profiles = product.get("dataAccess")
    if not isinstance(access_profiles, dict) or "$ref" in access_profiles:
        return []

    errors: list[str] = []
    for profile_name, access_profile in access_profiles.items():
        if not isinstance(access_profile, dict) or "$ref" in access_profile:
            continue
        contract_reference = access_profile.get("contract")
        if not isinstance(contract_reference, dict):
            continue
        reference = contract_reference.get("$ref")
        if not isinstance(reference, str) or not reference.startswith("#/"):
            continue
        parts = [part.replace("~1", "/").replace("~0", "~") for part in reference[2:].split("/")]
        if len(parts) != 3 or parts[:2] != ["product", "contract"]:
            errors.append(f"dataAccess.{profile_name}.contract must target one named Contract profile")
            continue
        target = pointer_value(document, reference)
        if not isinstance(target, dict):
            errors.append(f"dataAccess.{profile_name}.contract does not resolve to a Contract object")
    return errors


def load_conformance_fixture(failures: list[Failure], filename: str) -> tuple[Path, Any] | None:
    path = CONFORMANCE_FIXTURES / filename
    if not path.exists():
        failures.append(Failure("conformance-fixture", str(path.relative_to(ROOT)), "fixture is missing"))
        return None
    try:
        return path, load_yaml(path)
    except Exception as exc:  # noqa: BLE001
        failures.append(Failure("conformance-fixture", str(path.relative_to(ROOT)), str(exc).splitlines()[0]))
        return None


def resolve_local_conformance_reference(
    failures: list[Failure], source_path: Path, ref: str
) -> tuple[Path, Any] | None:
    if "://" in ref or ref.startswith("#"):
        failures.append(
            Failure("conformance-reference", str(source_path.relative_to(ROOT)), f"expected local package reference, got {ref}")
        )
        return None
    target = (source_path.parent / ref).resolve()
    fixture_root = CONFORMANCE_FIXTURES.resolve()
    if fixture_root not in target.parents or not target.exists():
        failures.append(
            Failure("conformance-reference", str(source_path.relative_to(ROOT)), f"package does not resolve: {ref}")
        )
        return None
    try:
        return target, load_yaml(target)
    except Exception as exc:  # noqa: BLE001
        failures.append(Failure("conformance-reference", str(target.relative_to(ROOT)), str(exc).splitlines()[0]))
        return None


def migrate_singleton_contract(document: dict[str, Any]) -> dict[str, Any]:
    """Reference migration used to prove the documented v4.1-to-v4.2 transformation."""
    migrated = deepcopy(document)
    product = migrated["product"]
    singleton = product["contract"]
    product["contract"] = {"default": singleton}
    migrated["schema"] = "https://opendataproducts.org/v4.2/schema/odps.yaml"
    migrated["version"] = 4.2
    return migrated


def validate_schema_conformance_fixtures(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    schemas = (("json", json_schema), ("yaml", yaml_schema))
    legacy = load_conformance_fixture(failures, "v4.1-singleton-contract.yml")
    migrated = load_conformance_fixture(failures, "v4.2-migrated-contract.yml")
    if legacy and migrated and isinstance(legacy[1], dict) and isinstance(migrated[1], dict):
        expect_schema_result(failures, "conformance-migration", str(legacy[0].relative_to(ROOT)), legacy[1], schemas, False)
        migrated_from_fixture = migrate_singleton_contract(legacy[1])
        if migrated_from_fixture != migrated[1]:
            failures.append(
                Failure("conformance-migration", str(migrated[0].relative_to(ROOT)), "migration output differs from expected fixture")
            )
        expect_schema_result(failures, "conformance-migration", str(migrated[0].relative_to(ROOT)), migrated[1], schemas, True)

    package_product = load_conformance_fixture(failures, "external-packages-product.yml")
    if package_product and isinstance(package_product[1], dict):
        product_path, product_document = package_product
        expect_schema_result(
            failures, "conformance-external-packages", str(product_path.relative_to(ROOT)), product_document, schemas, True
        )
        product = product_document.get("product", {})
        contract_ref = product.get("contract", {}).get("$ref") if isinstance(product, dict) else None
        access_ref = product.get("dataAccess", {}).get("$ref") if isinstance(product, dict) else None
        if isinstance(contract_ref, str):
            resolved = resolve_local_conformance_reference(failures, product_path, contract_ref)
            if resolved:
                _, package = resolved
                contract_schemas = tuple(
                    (name, standalone_subschema(schema, resolve_ref(schema, "#/$defs/ContractProfileCollection")))
                    for name, schema in schemas
                )
                expect_schema_result(
                    failures, "conformance-contract-package", str(resolved[0].relative_to(ROOT)), package, contract_schemas, True
                )
        else:
            failures.append(Failure("conformance-external-packages", str(product_path.relative_to(ROOT)), "contract package ref missing"))
        if isinstance(access_ref, str):
            resolved = resolve_local_conformance_reference(failures, product_path, access_ref)
            if resolved:
                _, package = resolved
                access_schemas = tuple(
                    (name, standalone_subschema(schema, resolve_ref(schema, "#/$defs/DataAccess")))
                    for name, schema in schemas
                )
                expect_schema_result(
                    failures, "conformance-data-access-package", str(resolved[0].relative_to(ROOT)), package, access_schemas, True
                )
        else:
            failures.append(Failure("conformance-external-packages", str(product_path.relative_to(ROOT)), "data access package ref missing"))

    invalid_package = load_conformance_fixture(failures, "invalid-data-access-package.yml")
    if invalid_package:
        access_schemas = tuple(
            (name, standalone_subschema(schema, resolve_ref(schema, "#/$defs/DataAccess"))) for name, schema in schemas
        )
        expect_schema_result(
            failures,
            "conformance-data-access-package",
            str(invalid_package[0].relative_to(ROOT)),
            invalid_package[1],
            access_schemas,
            False,
        )

    invalid_target = load_conformance_fixture(failures, "invalid-contract-target.yml")
    if invalid_target and isinstance(invalid_target[1], dict):
        expect_schema_result(
            failures, "conformance-contract-target", str(invalid_target[0].relative_to(ROOT)), invalid_target[1], schemas, True
        )
        if not contract_target_errors(invalid_target[1]):
            failures.append(
                Failure(
                    "conformance-contract-target",
                    str(invalid_target[0].relative_to(ROOT)),
                    "semantic validation accepted a reference to a non-Contract target",
                )
            )

    valid_target = load_conformance_fixture(failures, "valid-contract-access-target.yml")
    if valid_target and isinstance(valid_target[1], dict):
        expect_schema_result(
            failures, "conformance-contract-target", str(valid_target[0].relative_to(ROOT)), valid_target[1], schemas, True
        )
        semantic_errors = contract_target_errors(valid_target[1])
        if semantic_errors:
            failures.append(
                Failure(
                    "conformance-contract-target",
                    str(valid_target[0].relative_to(ROOT)),
                    "; ".join(semantic_errors),
                )
            )


def minimal_document() -> dict[str, Any]:
    return {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.yaml",
        "version": 4.2,
        "product": {
            "details": {
                "en": {
                    "name": "Contract profile validation product",
                    "productID": "contract-profile-validation",
                    "valueProposition": "Validates reusable data contract profiles.",
                    "description": "A focused validation fixture.",
                    "visibility": "public",
                    "status": "production",
                    "type": "dataset",
                    "productVersion": "1.0.0",
                }
            }
        },
    }


def with_product_fields(**fields: Any) -> dict[str, Any]:
    document = minimal_document()
    document["product"].update(fields)
    return document


def validate_contract_profile_feature(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    metadata_contract = {
        "id": "CONTRACT-001",
        "type": "ODCS",
        "contractVersion": "2.2.2",
        "contractURL": "https://example.org/contracts/default",
    }
    second_contract = {
        "id": "CONTRACT-002",
        "type": "ODCS",
        "contractVersion": "2.2.2",
        "contractURL": "https://example.org/contracts/internal",
    }
    valid_cases = {
        "default profile": with_product_fields(contract={"default": metadata_contract}),
        "several profiles": with_product_fields(
            contract={"default": metadata_contract, "internal": second_contract}
        ),
        "profile package reference": with_product_fields(
            contract={"$ref": "https://example.org/contracts/contract-profiles.yaml"}
        ),
        "individual profile reference": with_product_fields(
            contract={"default": {"$ref": "https://example.org/contracts/default.yaml"}}
        ),
        "inline profile spec": with_product_fields(
            contract={
                "default": {
                    "id": "CONTRACT-001",
                    "type": "ODCS",
                    "contractVersion": "2.2.2",
                    "spec": {"apiVersion": "v2.2.2"},
                }
            }
        ),
        "shared data access reference": with_product_fields(
            contract={"default": metadata_contract},
            dataAccess={
                "default": {
                    "outputPortType": "API",
                    "contract": {"$ref": "#/product/contract/default"},
                },
                "API": {
                    "outputPortType": "API",
                    "contract": {"$ref": "#/product/contract/default"},
                },
                "agent": {
                    "outputPortType": "AI",
                    "specification": "MCP",
                    "contract": {"$ref": "#/product/contract/default"},
                },
            },
        ),
        "data access package reference": with_product_fields(
            dataAccess={"$ref": "https://example.org/access/access-profiles.yaml"}
        ),
        "external data access profile": with_product_fields(
            dataAccess={
                "default": {"$ref": "https://example.org/access/default.yaml"},
                "API": {"outputPortType": "API"},
            }
        ),
    }
    invalid_cases = {
        "legacy singleton contract": with_product_fields(contract=metadata_contract),
        "profile collection without default": with_product_fields(contract={"internal": second_contract}),
        "contract profile unknown field": with_product_fields(
            contract={"default": {"id": "CONTRACT-001", "unexpected": "value"}}
        ),
        "contract package ref with sibling": with_product_fields(
            contract={"$ref": "https://example.org/contracts/profiles.yml", "default": metadata_contract}
        ),
        "data access without default": with_product_fields(
            dataAccess={"API": {"outputPortType": "API"}}
        ),
        "data access without output port type": with_product_fields(
            dataAccess={"default": {"accessURL": "https://example.org/api"}}
        ),
        "data access malformed URI": with_product_fields(
            dataAccess={"default": {"outputPortType": "API", "accessURL": "https://[invalid"}}
        ),
        "data access invalid language key": with_product_fields(
            dataAccess={"default": {"outputPortType": "API", "name": {"english": "Access"}}}
        ),
        "inline contract under data access": with_product_fields(
            dataAccess={
                "default": {
                    "outputPortType": "API",
                    "contract": {"id": "CONTRACT-001", "type": "ODCS"},
                }
            }
        ),
        "empty data access contract reference": with_product_fields(
            dataAccess={"default": {"outputPortType": "API", "contract": {}}}
        ),
        "data access contract ref with sibling": with_product_fields(
            dataAccess={
                "default": {
                    "outputPortType": "API",
                    "contract": {"$ref": "#/product/contract/default", "note": "not allowed"},
                }
            }
        ),
    }

    for case_name, instance in valid_cases.items():
        outcomes: list[bool] = []
        for schema_name, schema in (("json", json_schema), ("yaml", yaml_schema)):
            errors = list(Draft202012Validator(schema, format_checker=FORMAT_CHECKER).iter_errors(instance))
            outcomes.append(not errors)
            if errors:
                failures.append(
                    Failure(
                        "contract-profile-acceptance",
                        f"{case_name} ({schema_name})",
                        errors[0].message,
                    )
                )
        if len(set(outcomes)) != 1:
            failures.append(Failure("contract-profile-parity", case_name, "JSON and YAML schemas disagree"))
        validate_internal_refs(failures, "contract-profile-ref-resolution", case_name, instance)

    for case_name, instance in invalid_cases.items():
        outcomes = []
        for schema_name, schema in (("json", json_schema), ("yaml", yaml_schema)):
            accepted = not list(Draft202012Validator(schema, format_checker=FORMAT_CHECKER).iter_errors(instance))
            outcomes.append(accepted)
            if accepted:
                failures.append(
                    Failure(
                        "contract-profile-negative",
                        f"{case_name} ({schema_name})",
                        "invalid fixture was accepted",
                    )
                )
        if len(set(outcomes)) != 1:
            failures.append(Failure("contract-profile-parity", case_name, "JSON and YAML schemas disagree"))


def normalize_type(schema_node: dict[str, Any]) -> set[str]:
    value = schema_node.get("type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    if "oneOf" in schema_node:
        result: set[str] = set()
        for item in schema_node["oneOf"]:
            if isinstance(item, dict):
                result.update(normalize_type(item))
        return result
    return set()


def validation_keywords(value: Any) -> Any:
    """Remove documentation-only JSON Schema keywords before parity comparison."""
    if isinstance(value, dict):
        return {
            key: validation_keywords(child)
            for key, child in value.items()
            if key not in {"description", "examples"}
        }
    if isinstance(value, list):
        return [validation_keywords(child) for child in value]
    return value


def validate_schema_alignment(
    failures: list[Failure],
    json_schema: dict[str, Any],
    yaml_schema: dict[str, Any],
) -> None:
    Draft202012Validator.check_schema(json_schema)
    Draft202012Validator.check_schema(yaml_schema)

    if json_schema != yaml_schema:
        failures.append(
            Failure(
                "schema-representation-parity",
                "source/schema/odps.json and source/schema/odps.yaml",
                "JSON and YAML parsed schemas differ",
            )
        )
    if validation_keywords(json_schema) != validation_keywords(yaml_schema):
        failures.append(
            Failure(
                "schema-validation-parity",
                "source/schema/odps.json and source/schema/odps.yaml",
                "JSON and YAML schemas differ in validation keywords",
            )
        )

    for path in [(), ("product",)]:
        json_node = pointer(json_schema, path) if path else json_schema
        yaml_node = pointer(yaml_schema, path) if path else yaml_schema
        json_props = set(json_node.get("properties", {}))
        yaml_props = set(yaml_node.get("properties", {}))
        if json_props != yaml_props:
            failures.append(
                Failure(
                    "schema-property-alignment",
                    "/" + "/".join(path) if path else "/",
                    f"JSON-only {sorted(json_props - yaml_props)}; YAML-only {sorted(yaml_props - json_props)}",
                )
            )

    important_paths = [
        ("version",),
        ("product", "details"),
        ("product", "contract"),
        ("product", "SLA"),
        ("product", "dataQuality"),
        ("product", "pricingPlans"),
        ("product", "dataAccess"),
        ("product", "paymentGateways"),
        ("product", "license"),
        ("product", "dataHolder"),
    ]
    for path in important_paths:
        json_node = pointer(json_schema, path)
        yaml_node = pointer(yaml_schema, path)
        if not json_node or not yaml_node:
            failures.append(Failure("schema-node-alignment", "/" + "/".join(path), "missing in one schema"))
            continue
        json_type = normalize_type(json_node)
        yaml_type = normalize_type(yaml_node)
        if json_type and yaml_type and json_type.isdisjoint(yaml_type):
            failures.append(
                Failure(
                    "schema-type-alignment",
                    "/" + "/".join(path),
                    f"JSON type {sorted(json_type)} does not overlap YAML type {sorted(yaml_type)}",
                )
            )

    for definition in (
        "Contract",
        "ContractProfileCollection",
        "ContractProfiles",
        "ContractReference",
        "DataAccess",
        "DataAccessConfiguration",
        "DataAccessProfile",
        "DataAccessProfilePackageReference",
        "DataAccessProfileReference",
        "DataAccessItem",
        "Languages",
    ):
        json_node = json_schema.get("$defs", {}).get(definition)
        yaml_node = yaml_schema.get("$defs", {}).get(definition)
        if not json_node or not yaml_node:
            failures.append(Failure("schema-definition-alignment", definition, "missing in one schema"))

    for definition in (
        "Contract",
        "ContractProfilePackageReference",
        "ContractProfileCollection",
        "ContractProfiles",
        "ContractReference",
        "DataAccess",
        "DataAccessProfilePackageReference",
        "DataAccessConfiguration",
        "DataAccessProfileReference",
        "DataAccessProfile",
        "DataAccessItem",
        "Languages",
    ):
        json_node = json_schema.get("$defs", {}).get(definition)
        yaml_node = yaml_schema.get("$defs", {}).get(definition)
        if json_node and yaml_node and validation_keywords(json_node) != validation_keywords(yaml_node):
            failures.append(
                Failure(
                    "schema-validation-parity",
                    definition,
                    "JSON and YAML definitions differ in validation keywords",
                )
            )

    for definition in ("Contract", "ContractReference", "DataAccessItem"):
        json_node = resolve_ref(json_schema, f"#/$defs/{definition}")
        yaml_node = resolve_ref(yaml_schema, f"#/$defs/{definition}")
        json_props = set(json_node.get("properties", {}))
        yaml_props = set(yaml_node.get("properties", {}))
        if json_props != yaml_props:
            failures.append(
                Failure(
                    "schema-contract-field-alignment",
                    definition,
                    f"JSON-only {sorted(json_props - yaml_props)}; YAML-only {sorted(yaml_props - json_props)}",
                )
            )
        if set(json_node.get("required", [])) != set(yaml_node.get("required", [])):
            failures.append(Failure("schema-contract-required-alignment", definition, "required fields differ"))
        if json_node.get("additionalProperties") != yaml_node.get("additionalProperties"):
            failures.append(Failure("schema-contract-closure-alignment", definition, "additionalProperties differs"))

    for schema_name, schema in (("json", json_schema), ("yaml", yaml_schema)):
        collection = resolve_ref(schema, "#/$defs/ContractProfileCollection")
        if "default" not in collection.get("required", []):
            failures.append(
                Failure(
                    "schema-contract-default",
                    f"{schema_name} ContractProfileCollection",
                    "default profile is not required",
                )
            )
        contract_reference = resolve_ref(schema, "#/$defs/ContractReference")
        if contract_reference.get("required") != ["$ref"] or contract_reference.get("additionalProperties") is not False:
            failures.append(
                Failure(
                    "schema-contract-reference",
                    f"{schema_name} ContractReference",
                    "reference must require only $ref and reject extra properties",
                )
            )
        access_item = resolve_ref(schema, "#/$defs/DataAccessItem")
        if access_item.get("required") != ["outputPortType"]:
            failures.append(
                Failure(
                    "schema-data-access-output-port-type",
                    f"{schema_name} DataAccessItem",
                    "outputPortType must be required",
                )
            )
        if access_item.get("properties", {}).get("contract", {}).get("$ref") != "#/$defs/ContractReference":
            failures.append(
                Failure(
                    "schema-data-access-contract",
                    f"{schema_name} DataAccessItem",
                    "contract does not use ContractReference",
                )
            )
        access_collection = resolve_ref(schema, "#/$defs/DataAccess")
        if "default" not in access_collection.get("required", []):
            failures.append(
                Failure(
                    "schema-data-access-default",
                    f"{schema_name} DataAccess",
                    "default access profile is not required",
                )
            )


def validate_forbidden_drift(failures: list[Failure]) -> None:
    files = sorted(INCLUDES.glob("*.md")) + [SOURCE / "index.html.md", JSON_SCHEMA_PATH, YAML_SCHEMA_PATH]
    for path in files:
        text = read_text(path)
        for label, pattern in FORBIDDEN_TEXT_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                line = text[: match.start()].count("\n") + 1
                failures.append(Failure("forbidden-drift", f"{path.relative_to(ROOT)}:{line}", label))


def main() -> int:
    failures: list[Failure] = []
    json_schema = load_json(JSON_SCHEMA_PATH)
    yaml_schema = load_yaml(YAML_SCHEMA_PATH)

    try:
        validate_schema_alignment(failures, json_schema, yaml_schema)
    except Exception as exc:  # noqa: BLE001
        failures.append(Failure("schema-load", "source/schema", str(exc)))

    validate_markdown_yaml_examples(failures, json_schema, yaml_schema)
    validate_standalone_yaml_examples(failures, json_schema, yaml_schema)
    validate_template_family(failures, json_schema, yaml_schema)
    validate_hello_world_text_alignment(failures)
    validate_contract_profile_feature(failures, json_schema, yaml_schema)
    validate_schema_conformance_fixtures(failures, json_schema, yaml_schema)
    validate_forbidden_drift(failures)

    if failures:
        print(f"Spec alignment validation failed with {len(failures)} issue(s):")
        for failure in failures:
            print(f"- {failure.render()}")
        return 1

    print("Spec alignment validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
