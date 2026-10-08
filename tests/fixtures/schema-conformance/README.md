# ODPS 4.2 schema conformance fixtures

Run the complete suite with:

```text
python3 scripts/validate_spec_alignment.py
```

| Fixture or case | Expected outcome | What it proves |
|---|---|---|
| `v4.1-singleton-contract.yml` | Rejected by both v4.2 schemas | Singleton `product.contract` is no longer valid. |
| `v4.2-migrated-contract.yml` | Accepted by both schemas | The documented singleton-to-`default` migration produces the required profile shape. |
| `external-packages-product.yml` | Accepted by both schemas | Root Contract and Data Access references have the package wrapper shape. |
| `external-contract-profiles.yml` | Accepted as a Contract package by both schemas | A resolved external Contract package contains `default`. |
| `external-data-access-profiles.yml` | Accepted as a Data Access package by both schemas | A resolved external Data Access package contains `default` and typed profiles. |
| `invalid-data-access-package.yml` | Rejected by both schemas | A resolved Data Access package without `default` is invalid. |
| `valid-contract-access-target.yml` | Accepted by schemas and semantic validation | An access reference can target one named Contract profile. |
| `invalid-contract-target.yml` | Accepted by JSON Schema, rejected by semantic validation | An access reference must target one named Contract profile, not merely any existing pointer. |

The validator also contains generated negative cases for missing `default`, missing `outputPortType`, malformed URIs, invalid language keys, unknown Contract fields, package-reference siblings, inline Contracts under Data Access, and Contract-reference siblings.
