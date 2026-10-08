# ODPS 4.1 → 4.2 Migration Guide

ODPS 4.2 requires named Contract profiles. This is a breaking change for existing ODPS 4.1 documents that use a singleton `product.contract`: they must move that Contract under the required `default` profile.

## Required Contract migration

ODPS 4.1 used a singleton form:

```text
contract:
  id: CONTRACT-001
  type: ODCS
  contractVersion: 2.2.2
  contractURL: https://example.org/contracts/default
```

In ODPS 4.2, place the Contract object under the required `default` profile:

```yaml
contract:
  default:
    id: CONTRACT-001
    type: ODCS
    contractVersion: 2.2.2
    contractURL: https://example.org/contracts/default
```

Do not retain the singleton fields alongside `default`; the following shape is invalid:

```text
contract:
  id: CONTRACT-001
  default:
    id: CONTRACT-001
```

Additional named profiles are optional, but every inline Contract collection starts with `default`.

## Required Data Access migration

Every inline `dataAccess` collection must contain `default`. If an existing document has only a profile such as `API`, rename that profile to `default` or add a separate default access profile.

```text
# Invalid in ODPS 4.2: default is missing
dataAccess:
  API:
    outputPortType: API
```

```yaml
# Valid in ODPS 4.2
dataAccess:
  default:
    outputPortType: API
```

Each inline access profile must also declare `outputPortType`. A Data Access interface may then explicitly reference the Contract profile that governs it:

```yaml
dataAccess:
  default:
    outputPortType: API
    contract:
      $ref: '#/product/contract/default'
  API:
    outputPortType: API
    contract:
      $ref: '#/product/contract/default'
```

Additional named access profiles may be added for specific interfaces or audiences.

## External profile packages

A root `$ref` under `contract` always denotes an external Contract profile package. A root `$ref` under `dataAccess` always denotes an external Data Access profile package. In both cases, the resolved package MUST contain `default`.

```yaml
contract:
  $ref: https://example.org/contracts/contract-profiles.yaml

dataAccess:
  $ref: https://example.org/access/access-profiles.yaml
```

An individual named profile may also use `$ref`; it represents one profile, not a package:

```yaml
contract:
  default:
    $ref: https://example.org/contracts/default.yaml

dataAccess:
  default:
    $ref: https://example.org/access/default.yaml
```

## Migration checklist

1. Replace every singleton `product.contract` with `product.contract.default`.
2. Add `dataAccess.default` whenever `dataAccess` is inline.
3. Add `outputPortType` to every inline Data Access profile.
4. Keep Contract-to-Data-Access references as `$ref` objects; do not copy a complete Contract into an access profile.
5. Validate the completed document against the ODPS 4.2 JSON or YAML schema.

| ODPS 4.1 form | ODPS 4.2 behavior | Action required |
|---|---|---|
| Singleton `product.contract` | Invalid | Move the Contract under `contract.default` |
| Named contract profiles | Required when `contract` is used; inline collections require `default` | Use `default` and add named profiles as needed |
| Inline `dataAccess` without `default` | Invalid | Add or rename the primary interface to `default` |
| Inline Data Access profile without `outputPortType` | Invalid | Declare the delivery method, such as `file`, `API`, `SQL`, or `AI` |
| `dataAccess.<profile>.contract` | New reference-only binding | Add when an access interface must identify its contract profile |
| External Contract or Data Access package | Referenced package must contain `default` | Use a root `$ref` when profiles are governed outside the product document |

## Earlier ODPS 4.0 → 4.1 migration

ODPS 4.1 added the optional `productStrategy` object for business objectives, strategic alignment, product KPIs, and links to higher-level business KPIs. Existing 4.0 objects were not renamed or removed.

```yaml
productStrategy:
  objectives:
    - en: Enable smarter marketing campaigns
  contributesToKPI:
    id: KPI-OUT-001
    name: Retail Revenue Uplift
    unit: percent
    target: 5
    direction: increase
    timeframe: 2025-Q4
  productKPIs:
    - id: KPI-OUT-001-A
      name: Customer dataset usage
      unit: downloads
      target: 4000
```

Add the block under `product` only when business outcome alignment is needed.
