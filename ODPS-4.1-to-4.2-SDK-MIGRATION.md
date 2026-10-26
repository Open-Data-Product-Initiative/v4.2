# ODPS 4.2 SDK update guidance

## Purpose and status

[Certain] This is the current implementation guidance for SDKs that read, validate, generate, resolve, or transform ODPS 4.2 documents. It supersedes earlier guidance that described singleton Contract compatibility, ambiguous root Contract references, or separate JSON/YAML validation policies.

[Certain] ODPS 4.2 is a breaking change for the Contract shape. A v4.1 singleton `product.contract` is not a valid v4.2 document. An SDK may support a v4.1-to-v4.2 migration operation, but it must not silently accept the v4.1 shape as v4.2.

## Authoritative implementation inputs

At runtime, an SDK must use the deployed ODPS 4.2 schema URLs:

```text
https://opendataproducts.org/v4.2/schema/odps.json
https://opendataproducts.org/v4.2/schema/odps.yaml
```

The repository files below are the framework-maintenance sources for those deployed URLs:

| Input | Use it for |
|---|---|
| [`source/schema/odps.json`](source/schema/odps.json) | Canonical ODPS 4.2 schema representation |
| [`source/schema/odps.yaml`](source/schema/odps.yaml) | Generated YAML representation of the same schema |
| [`scripts/sync_schema_representations.py`](scripts/sync_schema_representations.py) | Regenerate YAML from JSON or detect drift |
| [`scripts/validate_spec_alignment.py`](scripts/validate_spec_alignment.py) | Executable JSON/YAML, example, fixture, URI, reference, and migration conformance checks |
| [`source/includes/_migration.md`](source/includes/_migration.md) | Reader-facing v4.1-to-v4.2 migration rules |
| [`tests/fixtures/schema-conformance`](tests/fixtures/schema-conformance) | Complete success and failure fixtures for SDK tests |

[Certain] The JSON and YAML schemas are identical after parsing. `odps.json` is canonical; do not maintain independent SDK validation behavior by schema file format.

## Contract model

`product.contract` is optional. When present, it has exactly two supported forms.

### Inline Contract profile collection

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/default
    restricted:
      id: CONTRACT-002
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/restricted
```

[Certain] An inline collection MUST contain `default`. Every named profile is a `Contract`; additional profile names are publisher-defined.

### External Contract profile package

```yaml
product:
  contract:
    $ref: https://example.org/contracts/contract-profiles.yaml
```

[Certain] A root Contract `$ref` always points to one external profile package, not to one individual Contract. The resolved package must validate as `ContractProfileCollection`, including its required `default` profile.

### Individual external Contract profile

```yaml
product:
  contract:
    default:
      $ref: https://example.org/contracts/default.yaml
```

[Certain] `product.contract.<profile>.$ref` points to one Contract. The SDK should preserve the profile name and resolve the referenced Contract when a caller requests resolution or semantic validation.

### Invalid v4.2 Contract shape

```text
product:
  contract:
    id: CONTRACT-001
    type: ODCS
```

[Certain] The singleton object above is invalid under both v4.2 schemas. It is a v4.1 input to an explicit migration operation, not a v4.2 compatibility branch.

## Data Access model

`product.dataAccess` is optional. When defined inline, it MUST contain `default` and every inline access profile MUST contain `outputPortType`.

```yaml
product:
  dataAccess:
    default:
      outputPortType: API
      format: JSON
      accessURL: https://example.org/api
    agent:
      outputPortType: AI
      specification: MCP
      format: MCP
```

The root may instead reference one external package:

```yaml
product:
  dataAccess:
    $ref: https://example.org/access/access-profiles.yaml
```

[Certain] A resolved Data Access package must validate as `DataAccess`, including `default`. An individual named access profile may also use a reference-only object:

```yaml
product:
  dataAccess:
    default:
      $ref: https://example.org/access/default.yaml
```

## Data Access-to-Contract relationship

An inline Data Access profile may identify its governing Contract profile:

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
  dataAccess:
    default:
      outputPortType: API
      contract:
        $ref: '#/product/contract/default'
```

[Certain] `dataAccess.<profile>.contract` is optional. If present, it is a closed `ContractReference`: it has exactly one required `$ref` field and no sibling fields. A complete Contract object is invalid at this location.

[Certain] Schema validation checks the reference wrapper and internal-pointer existence. An SDK that offers semantic validation must also verify that an internal access Contract reference targets exactly one named Contract profile, not merely any existing JSON Pointer target.

## SDK model and parsing requirements

Use a profile-oriented model. Do not expose a legacy singleton variant in the v4.2 model.

```text
ContractProfiles
├── InlineContractProfiles
│   ├── default: ContractProfile
│   └── additionalProfiles: Map<String, ContractProfile>
└── ExternalContractProfilePackageReference

DataAccessConfiguration
├── InlineDataAccessProfiles
│   ├── default: DataAccessProfile
│   └── additionalProfiles: Map<String, DataAccessProfile>
└── ExternalDataAccessProfilePackageReference

DataAccessProfile
├── InlineDataAccessItem
└── ExternalDataAccessProfileReference
```

Recommended parser behavior:

1. Select the schema from the document marker and configured version policy.
2. Validate the raw document against the canonical v4.2 schema.
3. Parse `product.contract` as either an inline collection or a root package reference.
4. Parse `product.dataAccess` as either an inline collection or a root package reference.
5. Preserve raw references, base URI, and source location for later resolution.
6. When semantic validation is requested, resolve internal pointers and permitted external targets, then validate their expected target types.

[Certain] A root Contract `$ref` requires no target-shape inference: it is always a Contract profile package. The SDK should not retain the former “singleton or package” resolver mode.

## Serialization and generation

Generated v4.2 documents must:

- write `contract.default` whenever they include a Contract;
- write `dataAccess.default` whenever they include inline Data Access;
- include `outputPortType` on every inline access profile;
- use reference-only Contract bindings from Data Access;
- write either canonical v4.2 schema URI (`https://opendataproducts.org/v4.2/schema/odps.json` or `https://opendataproducts.org/v4.2/schema/odps.yaml`) and the v4.2 version marker; and
- preserve a root `$ref` as a package reference rather than flattening it without an explicit resolution request.

[Likely] Serializers should preserve named-profile order when the source format preserves it, while treating `default` as the required primary profile rather than reordering arbitrary publisher-defined profiles.

## Explicit v4.1-to-v4.2 migration

Migration is a separate operation. It may accept a document routed to the v4.1 model, then perform the following deterministic Contract transformation:

```yaml
# v4.1 input
product:
  contract:
    id: CONTRACT-001
    type: ODCS
```

```yaml
# v4.2 output
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
```

Migration steps:

1. Parse and validate the input according to its declared v4.1 policy.
2. Wrap each singleton Contract in `product.contract.default`.
3. When inline Data Access lacks `default`, require caller-supplied migration policy. That policy may designate an existing profile to rename as `default` or supply an explicit default profile; otherwise fail with an actionable migration diagnostic.
4. Add missing `outputPortType` only when the caller supplies it or it can be determined without guesswork; otherwise fail with an actionable migration diagnostic.
5. Update the schema URI and version marker.
6. Do not invent Data Access-to-Contract bindings. Add them only when a caller provides the governing-profile mapping.
7. Validate the resulting document against ODPS 4.2 and report all remaining failures.

[Certain] A migration API must return diagnostics and the transformed document. It must not silently coerce a v4.1 document during ordinary v4.2 parse or validate calls.

## Reference resolution and security

Ordinary JSON Schema validation does not fetch arbitrary external data. SDK resolution should therefore be opt-in or policy-controlled and define:

- allowed schemes, hosts, and local-file roots;
- base URI and relative-reference handling;
- request timeouts, byte limits, recursion depth, and cycle detection;
- caching and cache invalidation;
- offline behavior and user-visible unresolved-reference diagnostics; and
- tenant isolation for fetched content and cache entries.

When resolving targets, validate them according to context:

| Reference location | Expected resolved target |
|---|---|
| `product.contract.$ref` | `ContractProfileCollection` containing `default` |
| `product.contract.<profile>.$ref` | One `Contract` |
| `product.dataAccess.$ref` | `DataAccess` collection containing `default` |
| `product.dataAccess.<profile>.$ref` | One `DataAccessItem` |
| `product.dataAccess.<profile>.contract.$ref` | One named Contract profile |

## Schema consumption policy

[Certain] Load either deployed v4.2 representation—`https://opendataproducts.org/v4.2/schema/odps.json` or `https://opendataproducts.org/v4.2/schema/odps.yaml`—according to SDK packaging needs; both have identical parsed contents. Do not add a runtime “JSON versus YAML schema” compatibility mode.

For framework maintenance:

```text
python3 scripts/sync_schema_representations.py --write
python3 scripts/sync_schema_representations.py
python3 scripts/validate_spec_alignment.py
```

The first command regenerates YAML from canonical JSON. The second fails when parsed representations differ. The third additionally validates the schema, all maintained examples and templates, 27 focused Contract/Data Access scenarios, fixture-local external package resolution, URI formats, and semantic Contract-target checks.

## SDK conformance suite

Import or reproduce the scenarios in [`tests/fixtures/schema-conformance/README.md`](tests/fixtures/schema-conformance/README.md).

Every schema case must run against both deployed v4.2 URLs. A case passes only when both representations produce the same accept/reject result. Diagnostics may differ in wording, but they must identify the same failing document location and rule class.

### Required acceptance set

| ID | Area | Input and assertion |
|---|---|---|
| `SCHEMA-01` | Schema parity | Load `https://opendataproducts.org/v4.2/schema/odps.json` and `https://opendataproducts.org/v4.2/schema/odps.yaml`; assert their parsed contents are equal. |
| `SCHEMA-02` | URI formats | Reject malformed `uri` and `uri-reference` values; accept absolute, relative, and fragment references where the schema allows them. |
| `CONTRACT-01` | Inline profiles | Accept `contract.default` with metadata, inline `spec`, and additional named profiles. |
| `CONTRACT-02` | Required default | Reject an inline Contract collection that omits `default`. |
| `CONTRACT-03` | Breaking change | Reject a v4.1 singleton Contract when validating as v4.2. |
| `CONTRACT-04` | Object closure | Reject unknown Contract fields and a root package `$ref` with sibling fields. |
| `CONTRACT-05` | External targets | Resolve a root Contract package and validate that it is a `ContractProfileCollection` containing `default`; resolve an individual profile reference as one Contract. |
| `ACCESS-01` | Inline profiles | Accept inline `dataAccess.default` with `outputPortType` and additional named access profiles. |
| `ACCESS-02` | Required default | Reject an inline Data Access collection that omits `default`. |
| `ACCESS-03` | Required output type | Reject any inline access profile that omits `outputPortType`. |
| `ACCESS-04` | External targets | Resolve a root Data Access package and validate `DataAccess.default`; resolve an individual access profile reference as one `DataAccessItem`. |
| `BINDING-01` | Valid Contract binding | Accept `dataAccess.<profile>.contract.$ref` targeting `#/product/contract/default` and another named profile. |
| `BINDING-02` | Reference closure | Reject an inline Contract under Data Access, an empty binding, and `$ref` with sibling fields. |
| `BINDING-03` | Target type | Reject an internal pointer that exists but points to `details`, a Contract property, or any value other than one named Contract profile. |
| `MIGRATE-01` | Contract conversion | Transform the v4.1 singleton fixture into the expected `contract.default` v4.2 fixture and validate the exact output against both v4.2 URLs. |
| `MIGRATE-02` | Non-invention | Verify migration does not create `dataAccess` profiles, infer `outputPortType`, or add Contract bindings without caller-provided policy. |
| `ROUNDTRIP-01` | Serialization | Parse, serialize, and parse valid inline-profile and external-reference documents without changing profile names, reference values, or base URI semantics. |
| `SECURITY-01` | Resolver controls | Reject or report blocked schemes/hosts, oversized responses, cycles, excessive depth, and references outside allowed local roots. |
| `DIAGNOSTIC-01` | Usability | Verify errors include the offending profile/access name and rule class (`missing-default`, `missing-output-port-type`, `invalid-contract-target`, or equivalent). |

### Test data and execution

Start with the framework fixtures:

- `v4.1-singleton-contract.yml` and `v4.2-migrated-contract.yml` for `MIGRATE-01`;
- `external-packages-product.yml`, `external-contract-profiles.yml`, and `external-data-access-profiles.yml` for successful package resolution;
- `invalid-data-access-package.yml` for a resolved package missing `default`;
- `valid-contract-access-target.yml` and `invalid-contract-target.yml` for semantic Contract-target validation; and
- the generated negative cases in `validate_spec_alignment.py` for closure, URI, language, and required-field assertions.

An SDK should vendor these fixtures or fetch them by an immutable release tag. Do not test only against hand-written SDK objects: load the actual YAML/JSON files so parsing, schema selection, reference bases, serialization, and diagnostics are exercised together.

### Completion evidence

For each SDK release that adds ODPS 4.2 support, retain:

1. the SDK version and commit;
2. the exact deployed schema URLs or pinned downloaded copies used in the run;
3. a pass/fail report for every acceptance-set ID;
4. the resolver policy used for external references; and
5. failing-document diagnostics for every negative test.

## Completion criteria

An SDK’s ODPS 4.2 update is complete only when:

1. its v4.2 parser rejects singleton Contracts and enforces required `default` profiles;
2. its generators and serializers produce the profile-oriented shape;
3. its optional resolver enforces the target types in the reference table above;
4. its migration command is explicit, deterministic, and does not invent governance relationships;
5. its validation diagnostics identify the failing profile, reference, or access interface;
6. its test suite executes the framework’s positive and negative conformance fixtures; and
7. it treats JSON and YAML schemas as identical representations of one ODPS 4.2 contract.
