# ODPS 4.1 → 4.2 Migration Guide

ODPS 4.2 is a minor, backward-compatible update. Existing ODPS 4.1 documents that use a singleton `product.contract` remain valid without modification.

## Migrating a singleton Data Contract

The ODPS 4.1 singleton form remains supported:

```yaml
contract:
  id: CONTRACT-001
  type: ODCS
  contractVersion: 2.2.2
  contractURL: https://example.org/contracts/default
```

For new ODPS 4.2 implementations, place the Contract object under the required `default` profile:

```yaml
contract:
  default:
    id: CONTRACT-001
    type: ODCS
    contractVersion: 2.2.2
    contractURL: https://example.org/contracts/default
```

Once profiles are used, a Data Access interface can explicitly reference the contract that governs it:

```yaml
dataAccess:
  API:
    outputPortType: API
    contract:
      $ref: '#/product/contract/default'
```

Migration to profiles is recommended when a product needs several reusable contractual contexts, when several interfaces share one contract, or when an explicit Data Access-to-contract relationship is needed. No migration is required solely to keep an existing singleton document valid.

| ODPS 4.1 form | ODPS 4.2 behavior | Action required |
|---|---|---|
| Singleton `product.contract` | Still valid for compatibility | None |
| Named contract profiles | New; inline collections require `default` | Use for new implementations |
| `dataAccess.<profile>.contract` | New reference-only binding | Add when an access interface must identify its contract profile |
| External contract profile package | New; referenced collection must contain `default` | Use when profiles are governed outside the product document |

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
