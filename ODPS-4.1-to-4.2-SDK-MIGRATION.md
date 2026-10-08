# ODPS 4.1 to 4.2 changes: foundation for updating the Data Product SDK

## Document purpose

[Certain] This document is an implementation-oriented account of the changes between the ODPS 4.1 baseline and the current ODPS 4.2 repository. Its purpose is to provide a reliable foundation for inspecting another repository and building a concrete plan to update the Data Product SDK.

[Certain] This is not yet the SDK implementation plan. The eventual plan must map the changes described here to the SDK repository's actual models, schema registry, parsers, reference resolver, validators, serializers, generators, CLI commands, MCP resources and tools, graph model, and tests.

### Authoritative comparison

| Item | Value |
|---|---|
| ODPS 4.1 baseline | `47ba96ea108b964241827e512dca25598c5f2ed9` (`upstream/main`) |
| ODPS 4.2 target | `d022f6236280f7a629b0832416aff4a3af4e3481` (`origin/main`) |
| Relationship | The v4.1 baseline is the direct parent of the four v4.2 commits |
| Primary feature commit | `452baf0` — `Add ODPS 4.2 data contract profiles` |
| Other commits | `e94ec35` build trigger; `d23fb25` framework/SDK introduction; `d022f62` SDK course and overview image |
| Machine-readable schemas | [`source/schema/odps.json`](source/schema/odps.json) and [`source/schema/odps.yaml`](source/schema/odps.yaml) |
| Executable conformance evidence | [`scripts/validate_spec_alignment.py`](scripts/validate_spec_alignment.py) |
| Migration prose | [`source/includes/_migration.md`](source/includes/_migration.md) |
| Release status | ODPS 4.2 is marked as under development and not yet a formal release in [`releases.md`](releases.md) |

[Certain] The comparison contains 36 changed tracked files: 825 insertions and 323 deletions. Only part of that diff is normative. The rest supplies examples, validation, migration guidance, version updates, or website content.

## Current specification status (2026-10-08)

[Certain] The original inventory below described the first v4.2 implementation. It has been superseded in three material ways:

1. `product.contract` no longer accepts an ODPS 4.1 singleton Contract. When it is inline, it is a named profile collection that MUST include `default`; a root `$ref` unambiguously denotes an external profile package.
2. `product.dataAccess` now requires `default` when it is inline. A root `$ref` denotes an external access-profile package that must contain `default`; a named profile may reference one external access profile.
3. The JSON and YAML schemas are now identical parsed schema representations. `source/schema/odps.json` is canonical and [`scripts/sync_schema_representations.py`](scripts/sync_schema_representations.py) produces the YAML representation; the validation gate rejects any drift.

[Certain] Consequently, references below to legacy singleton compatibility, root-reference ambiguity, or unresolved JSON/YAML differences are historical and must not be used for an SDK implementation.

## Executive summary

[Certain] ODPS 4.2 does not add or remove a top-level object under `product`. The important model change is that `product.contract` is no longer described only as one Contract object. It now accepts a configuration union containing:

1. the ODPS 4.1 singleton Contract form for compatibility;
2. an inline collection of named Contract profiles with a required `default` profile; or
3. a `$ref` to an external package of named Contract profiles.

[Certain] A Data Access item can now contain an optional, reference-only `contract` property. This allows an interface such as `API` or `agent` to identify the named Contract profile that governs it.

[Certain] The intended relationship is define once and reference many:

```text
product.contract.<profile>  <──  product.dataAccess.<interface>.contract.$ref
```

[Certain] Several Data Access interfaces may reference the same Contract profile, and different interfaces may reference different profiles.

[Certain] Common ODPS 4.1 singleton metadata documents remain accepted. However, the v4.2 schemas also tighten Contract validation, introduce new reference semantics, and expose compatibility edge cases. The SDK update must therefore be treated as a model and resolver change, not as a schema URL replacement.

[Likely] The safest SDK posture is:

- read both the v4.1 singleton and v4.2 profile forms;
- preserve the source form for lossless round trips;
- expose a normalized profile-oriented view internally;
- write the profile form for newly generated v4.2 documents;
- migrate singleton documents only through an explicit operation; and
- resolve root Contract references before deciding whether they represent one legacy Contract or a profile package.

## Change classification

| Layer | What changed | SDK relevance |
|---|---|---|
| Normative schemas | Contract configuration union, named profiles, package references, closed Contract objects, Data Access-to-Contract references | Direct implementation impact |
| Conformance tooling | Positive and negative feature cases, JSON/YAML parity checks, package validation, internal-pointer checks | Source for SDK acceptance tests |
| Examples and migration guidance | New profile, package, inline, external, and Data Access binding examples | Source for SDK fixtures and documentation |
| Version and reference corrections | Schema/version markers moved to 4.2; several internal JSON Pointer paths were corrected | Impacts version routing and resolver fixtures |
| Website and ecosystem copy | Framework/SDK explanation, promoted SDK course, v4.2 overview image, title/meta/link updates | No SDK data-model impact |

## 1. Version identity and schema routing

[Certain] The v4.2 repository changes schema descriptions, examples, page titles, schema URLs, source links, issue links, Open Graph metadata, templates, and documentation examples from 4.1 to 4.2.

The canonical v4.2 document markers used by the examples are:

```yaml
schema: https://opendataproducts.org/v4.2/schema/odps.yaml
version: 4.2
```

The JSON schema is available at:

```text
https://opendataproducts.org/v4.2/schema/odps.json
```

[Certain] Neither v4.2 schema constrains `version` to the literal value `4.2`. It remains a string-or-number field. The `schema` field is checked as a URI but is not constrained to the v4.2 URL.

### SDK consequence

[Certain] Successful schema validation alone does not identify the ODPS version. The SDK needs an explicit version-selection policy using the `schema` URI, the `version` value, caller configuration, or a controlled combination of them.

[Likely] If the URI and version disagree, the SDK should report the mismatch rather than silently choosing one.

## 2. Normative Contract model changes

### 2.1 `product.contract` now points to `ContractConfiguration`

ODPS 4.1 JSON schema:

```json
{
  "contract": {
    "type": "object",
    "$ref": "#/$defs/Contract"
  }
}
```

ODPS 4.2:

```json
{
  "contract": {
    "type": "object",
    "$ref": "#/$defs/ContractConfiguration"
  }
}
```

[Certain] `ContractConfiguration` is a `oneOf` union between a compatible legacy singleton and `ContractProfiles`.

### 2.2 The individual `Contract` object is now closed and non-empty

The permitted fields remain:

| Field | Type or constraint | Meaning |
|---|---|---|
| `$ref` | string, `uri-reference` | Loads one individual Contract definition when used inside a named profile |
| `id` | string | Contract identifier |
| `type` | `ODCS` or `DCS` | Contract standard |
| `contractVersion` | string | Version of the Contract standard |
| `contractURL` | absolute URI | Location in a Contract management service or similar system |
| `spec` | object | Inline Contract content |

[Certain] ODPS 4.2 adds `minProperties: 1` and `additionalProperties: false` to `Contract`.

Consequences:

- an empty Contract is invalid;
- unknown Contract fields are invalid;
- at least one recognized field is sufficient at schema level;
- the schemas do not require the full metadata set of `id`, `type`, `contractVersion`, and `contractURL`; and
- a named profile may use metadata, an inline `spec`, an individual `$ref`, or a permitted combination.

[Certain] The Contract `$ref` format changed from `uri` to `uri-reference`. This admits relative references and fragment references in addition to absolute URIs.

### 2.3 New Contract definitions

| Definition | Exact role |
|---|---|
| `ContractProfilePackageReference` | A closed object containing only a required `$ref`; it represents an external package of profiles |
| `ContractProfileCollection` | An inline map of Contract profiles; `default` is required and every additional key must validate as `Contract` |
| `ContractProfiles` | A union of an inline `ContractProfileCollection` and a `ContractProfilePackageReference` |
| `ContractConfiguration` | A union of a legacy singleton Contract without a root `$ref` and `ContractProfiles` |
| `ContractReference` | A closed, reference-only object used from a Data Access item; `$ref` is required |

### 2.4 Inline named profiles

Recommended v4.2 form:

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

[Certain] `default` is required only when `product.contract` is an inline profile collection. Additional profile names are publisher-defined and are not restricted by a naming pattern in the schemas.

### 2.5 External individual profile

```yaml
product:
  contract:
    default:
      $ref: https://example.org/contracts/default.yaml
```

[Certain] At `product.contract.<profile>.$ref`, the referenced target represents one Contract.

### 2.6 External profile package

```yaml
product:
  contract:
    $ref: https://example.org/contracts/contract-profiles.yaml
```

The referenced package has the collection shape rather than a complete ODPS document:

```yaml
default:
  id: CONTRACT-001
  type: ODCS
  contractVersion: 2.2.2
  contractURL: https://example.org/contracts/default
internal:
  id: CONTRACT-002
  type: ODCS
  contractVersion: 2.2.2
  contractURL: https://example.org/contracts/internal
```

[Certain] The package must contain `default`. JSON Schema validation of the containing ODPS document does not fetch and validate this data target. The repository validates its local package fixture separately against `ContractProfileCollection`.

### 2.7 Legacy singleton compatibility

The ODPS 4.1 metadata form remains accepted:

```yaml
product:
  contract:
    id: CONTRACT-001
    type: ODCS
    contractVersion: 2.2.2
    contractURL: https://example.org/contracts/default
```

[Certain] The legacy branch explicitly excludes a root object containing `$ref`. A root `$ref` is routed by the v4.2 schema to the external profile-package branch.

[Certain] The specification prose nevertheless states that a legacy external singleton `$ref` and a v4.2 external profile-package `$ref` share the same wrapper shape. Tools that support legacy external singleton references must resolve the target and distinguish:

- one Contract object; from
- a profile collection containing `default`.

[Certain] This ambiguity cannot be resolved from the wrapper alone.

## 3. Data Access changes

### 3.1 New optional `contract` property

A v4.2 Data Access item may bind itself to a named Contract profile:

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
    restricted:
      id: CONTRACT-002
  dataAccess:
    API:
      outputPortType: API
      contract:
        $ref: '#/product/contract/default'
    agent:
      outputPortType: AI
      specification: MCP
      format: MCP
      contract:
        $ref: '#/product/contract/default'
    restrictedAPI:
      outputPortType: API
      contract:
        $ref: '#/product/contract/restricted'
```

[Certain] `dataAccess.<interface>.contract` uses `ContractReference` and is optional.

[Certain] If present, it must be an object with exactly one required `$ref` field. An inline Contract object is invalid at this location, and extra sibling properties are invalid.

[Certain] The schemas accept any syntactically valid URI reference here. The examples use internal JSON Pointers to named profiles.

### 3.2 Relationship semantics

[Certain] The new reference expresses which contractual context governs one access interface. It does not copy or override the Contract.

[Certain] Cardinality is many-to-one from access interfaces to Contract profiles:

- several access interfaces may point to one profile;
- one product may define several profiles; and
- each access item has at most one `contract` reference in the current model.

### 3.3 What did not change

[Certain] `product.dataAccess` remains a map of publisher-named interfaces. Existing access fields such as `name`, `description`, `outputPortType`, `format`, `authenticationMethod`, `specification`, URLs, hash type, and checksum remain.

[Certain] No Data Access-to-Contract binding is required. Existing Data Access entries do not need a `contract` binding solely to use v4.2, although validation outcomes can still differ because the YAML-authored v4.2 schema now declares and constrains the full Data Access field set.

## 4. Reference behavior the SDK must implement

### 4.1 Reference locations have different target types

| Location | Expected target |
|---|---|
| `product.contract.$ref` | A profile package in new v4.2 documents; potentially one legacy external Contract when compatibility resolution is enabled |
| `product.contract.<profile>.$ref` | One Contract object |
| `product.dataAccess.<interface>.contract.$ref` | A named Contract profile, normally inside the current ODPS document |
| Pricing/SLA/DQ/access/payment references | Existing reusable ODPS components; correct internal paths begin at `#/product/...` |

### 4.2 Internal pointers

[Certain] The repository validator checks whether internal `$ref` pointers resolve to an existing location and decodes JSON Pointer escapes `~1` and `~0`.

[Certain] Its internal-pointer check verifies existence, not that a Data Access Contract reference resolves specifically to a Contract profile. That target-type check remains an SDK responsibility if semantic validation is required.

### 4.3 External targets

[Certain] The repository's schema validator does not fetch arbitrary external data references. External profile-package and individual-profile semantics therefore require a resolver above ordinary JSON Schema validation.

[Certain] Existing ODPS prose also shows reference-only wrappers for components such as Data Access and Payment Gateway packages. The repository validator deliberately skips some reference-only objects and maps instead of validating those wrappers against the component subschema. The SDK update must preserve or deliberately revise its existing generic component-reference behavior; the new Contract definitions do not automatically regularize every older `$ref` convention.

[Likely] A production SDK resolver should define:

- supported schemes and local-file behavior;
- base-URI handling for relative references;
- request timeouts and maximum response size;
- recursion depth and cycle detection;
- caching and cache invalidation;
- offline behavior;
- tenant and network isolation; and
- whether external content is retained verbatim, normalized, or both.

## 5. Compatibility matrix

[Certain] The following matrix was reproduced against the v4.1 JSON schema, v4.1 YAML-authored schema, v4.2 JSON schema, and v4.2 YAML-authored schema with JSON Schema Draft 2020-12 validation and format checking.

| Input shape | 4.1 JSON | 4.1 YAML schema | 4.2 JSON | 4.2 YAML schema | Interpretation |
|---|---:|---:|---:|---:|---|
| Full legacy singleton metadata | Pass | Pass | Pass | Pass | Supported compatibility path |
| Root `$ref` only | Pass | Fail | Pass | Pass | Ambiguous legacy-singleton/package wrapper in v4.2 |
| Root `$ref` plus full singleton metadata | Pass | Pass | Fail | Fail | Tightened by the v4.2 union and closed package reference |
| Empty Contract object | Pass | Fail | Fail | Fail | v4.2 requires at least one Contract property |
| Full singleton plus unknown field | Pass | Pass | Fail | Fail | v4.2 closes `Contract` to known fields |
| Inline `default` profile | Pass accidentally | Fail | Pass | Pass | Semantically introduced and aligned in v4.2 |
| Inline profiles without `default` | Pass accidentally | Fail | Fail | Fail | Explicitly invalid in v4.2 |
| Inline Contract under Data Access | Pass as an unknown field | Pass as an unknown field | Fail | Fail | v4.2 permits only `ContractReference` at this location |
| Data Access Contract `$ref` with extra siblings | Pass as an unknown field | Pass as an unknown field | Fail | Fail | `ContractReference` is closed |

[Certain] “Pass accidentally” means the v4.1 JSON schema accepted the shape because Contract objects were open, not because v4.1 defined named profiles.

### Compatibility conclusion

[Certain] Ordinary singleton metadata and inline `spec` forms have a clear compatibility path. Root `$ref` wrappers are accepted by both v4.2 schemas, but legacy interpretation still requires target resolution. This is not a guarantee that every object accepted by either v4.1 schema is accepted unchanged by v4.2.

[Certain] In particular, permissive or mixed Contract objects can fail after the upgrade. The SDK needs regression fixtures for these edges and must not describe validation as universally backward-compatible without qualification.

## 6. JSON/YAML schema alignment and remaining specification decisions

### 6.1 Improvements in v4.2

[Certain] Both v4.2 schemas now contain the new Contract definitions and the Data Access `contract` reference. The repository validator confirms field, required-key, and closed-object alignment for `Contract` and `ContractReference`, requires `default` in both profile-collection definitions, and tests the same feature fixtures against both schemas.

[Certain] The YAML-authored schema now defines the full Data Access item property set rather than only `outputPortType`. This means its declared fields now receive type, enum, and URI-format validation closer to the JSON schema.

### 6.2 Remaining differences that the SDK plan must not ignore

#### `outputPortType`

[Certain] `DataAccessItem.outputPortType` is required in the YAML-authored v4.2 schema but not required in the JSON v4.2 schema. This difference already existed in v4.1 and remains unresolved.

#### `dataAccess.default`

[Certain] The Data Access prose says `default` must be present when `dataAccess` is used. Neither v4.2 schema requires that key, and the v4.2 feature validator intentionally accepts access maps containing only `API` and `agent`.

#### Contract metadata completeness

[Certain] The prose commonly presents `id`, `type`, `contractVersion`, and `contractURL` together, but the v4.2 schemas require only that a Contract contain at least one recognized property.

#### Release maturity

[Certain] The site is deployed, but `releases.md` still declares v4.2 under development and not a formal release.

### Required planning decisions

Before implementation, the SDK project should explicitly decide:

1. whether `outputPortType` is mandatory in the SDK model or only in a strict validation mode;
2. whether `dataAccess.default` is enforced, warned about, or left unconstrained;
3. whether partial Contract metadata is accepted exactly as the schemas permit;
4. how preview v4.2 support is labelled and versioned; and
5. which schema representation is used at runtime when the official JSON and YAML-authored schemas disagree.

## 7. Executable conformance behavior added in v4.2

[`scripts/validate_spec_alignment.py`](scripts/validate_spec_alignment.py) now supplies the clearest executable statement of feature intent.

### Positive cases

Both v4.2 schemas must accept:

- a legacy singleton Contract;
- an inline collection containing `default`;
- several named profiles;
- a root profile-package `$ref`;
- an individual profile `$ref`;
- an inline profile `spec`; and
- several Data Access interfaces sharing one Contract profile reference.

### Negative cases

Both schemas must reject:

- an inline profile collection without `default`;
- an inline Contract object under a Data Access item; and
- an empty Data Access Contract reference.

### Other validator additions

The validator now:

- identifies v4.2 documents and examples;
- validates complete documentation examples against both schemas;
- validates component examples against their subschemas;
- validates the external profile-package fixture against `ContractProfileCollection`;
- verifies JSON/YAML presence of the new definitions;
- verifies Contract field and closure alignment;
- checks internal reference existence;
- materializes and validates all linked templates as v4.2 documents; and
- rejects selected stale field names and reference patterns in specification prose and schemas.

## 8. Example and documentation changes relevant to the SDK

### New focused fixtures

| File | Behavior represented |
|---|---|
| [`contract-profiles.yml`](source/examples/DataContract/contract-profiles.yml) | Inline `default` and `internal` profiles |
| [`contract-access-reference.yml`](source/examples/DataContract/contract-access-reference.yml) | Several access interfaces bound to reusable profiles |
| [`contract-external-profile.yml`](source/examples/DataContract/contract-external-profile.yml) | One named profile loading an external Contract |
| [`contract-profiles-package.yml`](source/examples/DataContract/contract-profiles-package.yml) | Standalone external profile collection |
| [`datacontract-inline.yml`](source/examples/DataContract/datacontract-inline.yml) | Inline Contract content beneath `default` |
| [`datacontract-url.yml`](source/examples/DataContract/datacontract-url.yml) | Metadata and Contract service URL beneath `default` |

### Updated complete example

[Certain] The Hello World example now:

- uses the v4.2 schema URI and version;
- defines `default` and `internal` Contract profiles;
- binds both API and MCP/agent access interfaces to `#/product/contract/default`; and
- identifies ODPS 4.2 in its standards list.

### Reference-path corrections

[Certain] Several examples and prose references were corrected to start from the actual document root, for example:

```text
#/product/paymentGateways/default
#/product/dataQuality/...
#/product/SLA/...
#/product/dataAccess/API
#/product/contract/default
```

[Certain] The exact SLA and Data Quality pointer depth depends on the instance shape. The Hello World example uses `declarative` in those paths, while another reference fixture defines profiles directly beneath `SLA` and `dataQuality`. An SDK resolver must follow the document rather than hard-code one abbreviated path.

### Templates

[Certain] All eight maintained template-family YAML files now identify v4.2. Their product-domain content is otherwise unchanged by this version bump.

## 9. Required SDK impact analysis

The following areas must be inspected in the Data Product SDK repository before writing the implementation plan.

| SDK area | Required investigation or change |
|---|---|
| Version registry | Add v4.2 schema URIs and define mismatch behavior for `schema` versus `version` |
| Data model | Replace a singleton-only Contract type with a discriminated configuration supporting legacy singleton, profile collection, and external package reference |
| Profile model | Represent required `default`, arbitrary additional profile names, and individual external profile references |
| Data Access model | Add optional reference-only `contract` to each access item |
| Parser | Detect shapes without confusing legacy singleton fields with profile names |
| Serializer | Preserve input shape for round trips; emit recommended profiles for new v4.2 generation |
| Reference resolver | Resolve internal pointers, relative references, external individual Contracts, and external profile packages |
| Semantic validator | Validate resolved package shape, required `default`, Data Access target existence/type, cycles, and version/schema coherence |
| JSON Schema validator | Load the v4.2 schema selected by policy and retain diagnostics from the exact schema used |
| Migration API | Offer explicit singleton-to-`default` transformation without silently changing existing documents |
| Generator/templates | Generate v4.2 markers, named profiles, and optional access bindings |
| Graph/traversal | Add Contract-profile nodes or indexed objects and `governed by` edges from access interfaces |
| Search/indexing | Index profile name, Contract type/version/URL, reference target, and bound interfaces |
| CLI | Review `validate`, `generate`, `convert`, `explain`, `inspect`, `resolve`, and migration commands |
| MCP | Review resources/tools that expose schema definitions, generate ODPS, traverse references, or explain Data Access and Contract relationships |
| Error model | Add specific errors for missing `default`, invalid Contract shape, invalid reference wrapper, unresolved target, wrong target type, and cycles |
| Caching/security | Define safe external-reference fetching and tenant-isolated caches |
| Tests | Import official fixtures and add SDK-specific parser, round-trip, resolver, CLI, and MCP tests |

## 10. Recommended internal representation

[Likely] A useful normalized model is conceptually:

```text
ContractConfiguration
├── LegacySingletonContract
├── InlineContractProfiles
│   ├── default: Contract
│   └── additional profiles: Map<String, Contract>
└── ExternalContractProfilePackageRef

DataAccessItem
└── contract: Optional<ContractReference>
```

[Likely] The normalized API may expose a legacy singleton as an effective `default` profile for consumers, but it should retain origin metadata so serialization can reproduce the original singleton unless migration was explicitly requested.

[Certain] A raw dictionary alone is insufficient if the SDK must distinguish the three root Contract forms, produce precise errors, or traverse profile relationships.

## 11. Suggested migration algorithm for SDK users

This describes expected migration behavior, not an authorization to implement it before inspecting the SDK repository.

1. Parse the document without changing it.
2. Determine the intended ODPS version from configured policy, schema URI, and version marker.
3. Classify `product.contract`:
   - known singleton fields without `default` → legacy singleton;
   - `default` plus optional profile keys → inline profile collection;
   - root `$ref` only → unresolved legacy singleton or profile-package reference.
4. Resolve a root `$ref` when classification affects behavior.
5. Validate the resolved target as one Contract or `ContractProfileCollection`.
6. For an explicit v4.1-to-v4.2 migration, wrap a singleton under `default`.
7. Update the schema URI and version marker to 4.2.
8. Add Data Access Contract bindings only when the governing profile is known; do not invent relationships.
9. Validate schema constraints, internal pointers, resolved external targets, and cross-object semantics.
10. Serialize deterministically and verify a parse-serialize-parse round trip.

Example explicit transformation:

```yaml
# Before: v4.1 singleton
product:
  contract:
    id: CONTRACT-001
    type: ODCS
    contractVersion: 2.2.2
    contractURL: https://example.org/contracts/default
```

```yaml
# After: recommended v4.2 profile form
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/default
```

[Certain] This structural migration alone does not justify adding a Data Access binding. That relationship requires domain knowledge about which Contract governs each interface.

## 12. Minimum SDK conformance suite

### Parsing and validation

- legacy singleton metadata;
- singleton with inline `spec`;
- inline `default` profile;
- several profiles;
- missing `default` rejection;
- empty Contract rejection;
- unknown Contract field rejection;
- root package `$ref`;
- relative and fragment Contract references;
- individual profile `$ref`;
- mixed root `$ref` plus singleton metadata rejection;
- Data Access Contract reference acceptance;
- inline Data Access Contract rejection;
- empty or extra-field Contract reference rejection.

### Resolution

- valid internal pointer to `default`;
- valid pointer to a non-default profile;
- several access interfaces sharing one profile;
- missing internal target;
- target exists but is not a Contract profile;
- JSON Pointer keys requiring `~0` and `~1` decoding;
- valid external individual Contract;
- valid external package with `default`;
- external package missing `default`;
- ambiguous root `$ref` resolving to one legacy Contract;
- ambiguous root `$ref` resolving to a profile package;
- reference cycle;
- maximum-depth and maximum-size enforcement;
- offline/cache behavior.

### Serialization and migration

- lossless round trip of v4.1 singleton form;
- lossless round trip of v4.2 profile form;
- deterministic profile ordering policy;
- explicit singleton-to-default migration;
- no automatic access bindings;
- preservation of inline `spec` content;
- preservation or controlled normalization of relative references.

### User-facing surfaces

- CLI diagnostics identify the failing profile or access interface;
- CLI/MCP explain the effective Contract for an interface;
- generated v4.2 documents use the v4.2 schema URI and version;
- MCP resources expose profile identity and relationship targets without flattening away evidence;
- graph traversal can move from an access interface to its governing Contract profile.

## 13. Acceptance criteria for the eventual SDK update

The SDK update should not be considered complete until:

1. v4.1 singleton documents still load, validate according to the declared policy, and round-trip;
2. all official positive v4.2 Contract-profile fixtures load and validate;
3. all official negative fixtures fail for the intended reason;
4. root `$ref` ambiguity is handled deliberately and tested;
5. Data Access Contract references resolve and are exposed through SDK, CLI, graph, and MCP surfaces that already expose Data Access;
6. external package content is validated as a profile collection with `default`;
7. generators produce recommended v4.2 profile structures;
8. migration is explicit and does not invent access-to-contract relationships;
9. JSON/YAML schema differences have an explicit SDK policy;
10. schema/version mismatch behavior is documented and tested;
11. security limits for external resolution are implemented; and
12. SDK documentation clearly separates ODPS normative behavior from SDK convenience normalization.

## 14. Complete repository change inventory

### Normative schemas

- `source/schema/odps.json`
- `source/schema/odps.yaml`

### Validation tooling

- `scripts/validate_spec_alignment.py`

### Data Contract examples

- `source/examples/DataContract/contract-access-reference.yml` — added
- `source/examples/DataContract/contract-external-profile.yml` — added
- `source/examples/DataContract/contract-profiles-package.yml` — added
- `source/examples/DataContract/contract-profiles.yml` — added
- `source/examples/DataContract/datacontract-inline.yml` — rewritten as a focused v4.2 profile example
- `source/examples/DataContract/datacontract-url.yml` — rewritten as a focused v4.2 profile example

### Reference examples

- `source/examples/Refs/urbanpulse_basic.yml` — version/schema marker update
- `source/examples/Refs/urbanpulse_internal.yml` — version/schema update and root-corrected internal pointers

### Template family

- `source/examples/Templates/maturity-product-brief.yml`
- `source/examples/Templates/maturity-product-definition.yml`
- `source/examples/Templates/maturity-product-operating-model.yml`
- `source/examples/Templates/purpose-agentic-product.yml`
- `source/examples/Templates/purpose-analytical-product.yml`
- `source/examples/Templates/purpose-marketplace-product.yml`
- `source/examples/Templates/purpose-product-profile.yml`
- `source/examples/Templates/purpose-reusable-data-product.yml`

[Certain] These eight template files changed only their schema URI and version markers in the v4.1-to-v4.2 comparison.

### Specification prose and examples

- `source/includes/_bareminimum.md`
- `source/includes/_dataaccess.md`
- `source/includes/_datacontract.md`
- `source/includes/_details.md`
- `source/includes/_example_inline.md`
- `source/includes/_gateways.md`
- `source/includes/_helloworld.md`
- `source/includes/_migration.md`
- `source/includes/_strategy.md`
- `source/index.html.md`

### Repository and planning documentation

- `CHANGELOG.md`
- `README.md`
- `releases.md`
- `drafts/medium-odps-template-family.md`
- `drafts/odps-template-family-plan.md`

### Website-only presentation

- `source/layouts/layout.erb` — v4.2 icon source, title, canonical page metadata, and URL updates
- `source/images/ODPS-design.png` — v4.2 overview image

[Certain] The framework/SDK introduction and promoted SDK course in `source/index.html.md`, along with the overview image, affect communication and presentation but do not change ODPS instance semantics.

## 15. Evidence and reproducibility

The repository comparison can be reproduced with:

```bash
git fetch origin
git fetch upstream
git merge-base upstream/main origin/main
git log --oneline upstream/main..origin/main
git diff --name-status upstream/main..origin/main
git diff upstream/main..origin/main -- source/schema/odps.json
git diff upstream/main..origin/main -- source/schema/odps.yaml
python3 scripts/validate_spec_alignment.py
```

[Certain] At the time this document was prepared, `python3 scripts/validate_spec_alignment.py` passed, the Middleman site built successfully with a compatible temporary FFI runtime, and the v4.2 deployment workflow completed successfully.

## 16. Inputs needed before writing the SDK implementation plan

The next project should be inspected for:

- current supported ODPS versions and schema download/cache mechanism;
- Contract and Data Access classes or typed dictionaries;
- use of generated models from JSON Schema;
- parser shape-discrimination logic;
- serializer and round-trip guarantees;
- internal and external `$ref` resolution;
- schema versus semantic validation layers;
- migration/conversion commands;
- fixture and golden-file locations;
- CLI commands that read, validate, explain, generate, or resolve ODPS;
- MCP tools/resources/prompts backed by ODPS;
- graph or relationship traversal;
- search/index fields;
- external network and tenant-isolation rules; and
- release/versioning policy for preview specification support.

[Certain] Only after those surfaces are mapped can this foundation be converted into a scoped, repository-specific SDK update plan with file-level tasks, compatibility gates, and test evidence.
