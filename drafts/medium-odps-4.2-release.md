# ODPS 4.2: Making Data Contracts Reusable and Explicit

ODPS 4.2 is a focused release, not a broad redesign of the Open Data Product Specification. The main change is how a data product declares the contracts that govern it.

In ODPS 4.1, `product.contract` described one Contract. That works when a product has a single contractual context. It becomes limiting when the same product serves several audiences, delivery channels, or governance contexts. An internal API, a partner data share, and a restricted analyst export can have different contracts, while still belonging to the same data product.

ODPS 4.2 makes those contexts explicit and reusable.

## What changes from ODPS 4.1

### 1. A Contract is now a named profile collection

The v4.1 singleton Contract form is replaced by a collection of named Contract profiles. Every inline collection must contain a `default` profile. Publishers can then add profiles such as `internal`, `partner`, or `restricted` when those names reflect real contractual contexts.

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/default
    partner:
      id: CONTRACT-002
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/partner
```

The individual profile still uses the established Contract fields: `id`, `type`, `contractVersion`, `contractURL`, and optional inline `spec`. ODPS 4.2 does not introduce a second Contract model. It introduces a way to name and reuse contractual contexts.

### 2. Data Access can identify its governing Contract

An access interface can now reference the Contract profile that governs it. The reference is deliberately reference-only: a complete Contract must not be copied under `dataAccess`.

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/default
  dataAccess:
    default:
      outputPortType: API
      contract:
        $ref: '#/product/contract/default'
    partner-api:
      outputPortType: API
      contract:
        $ref: '#/product/contract/partner'
```

This gives a product one authoritative definition of each Contract profile, while allowing several access interfaces to point to it. It avoids duplication and makes the relationship between delivery and contractual obligations machine-readable.

### 3. Profile packages can live outside the product document

Contract and Data Access profiles can be maintained as reusable external packages. At the root of `contract` or `dataAccess`, a `$ref` refers to a complete profile package, which must contain `default`. Inside a named collection, a `$ref` refers to one individual profile.

That distinction matters. It lets teams publish shared profiles centrally without making an external package ambiguous with an individual Contract or access interface.

### 4. Inline Data Access has clearer minimum requirements

ODPS 4.2 makes rules that were often implied by examples explicit in the schema:

- an inline `dataAccess` collection must contain `default`;
- each inline access profile must declare `outputPortType`; and
- a Data Access-to-Contract link must be a `$ref` object with no copied Contract fields beside it.

These rules make documents easier for validators, catalogs, SDKs, and automation to interpret consistently.

## The important migration implication

This is a breaking change for documents that use the ODPS 4.1 singleton Contract form. A v4.1 document such as this:

```yaml
product:
  contract:
    id: CONTRACT-001
    type: ODCS
    contractVersion: 2.2.2
    contractURL: https://example.org/contracts/default
```

must become:

```yaml
product:
  contract:
    default:
      id: CONTRACT-001
      type: ODCS
      contractVersion: 2.2.2
      contractURL: https://example.org/contracts/default
```

Migration should be explicit. It is safe to move a known singleton Contract under `default`; it is not safe for a tool to invent a Data Access-to-Contract relationship or guess a missing `outputPortType`.

## What did not change

ODPS 4.2 does not replace the broader product model introduced in v4.1. The `productStrategy` object, including business objectives and KPIs, remains part of the specification. So do the existing product areas for details, data quality, SLA, pricing, licensing, and governance.

The release also does not turn the Data Product Operating Framework or the Open Data Products SDK into normative parts of ODPS. The framework helps organizations direct, define, operate, and assure data products; the SDK provides implementation tooling. ODPS remains the machine-readable specification for an individual product.

## What is included in ODPS 4.2

ODPS 4.2 contains more than prose describing the new model:

- JSON and YAML schemas express the same profile-oriented rules;
- examples cover inline profiles, individual external profiles, external profile packages, and Data Access bindings;
- the migration guide identifies the required structural changes from v4.1; and
- conformance fixtures test valid profile collections, missing `default` profiles, missing access types, external packages, and valid and invalid Contract-reference targets.

This is important for implementers. A profile model is only useful if a document validates the same way across its JSON and YAML schema representations and if tools can distinguish a valid reference from a pointer that merely happens to exist.

## Why this release matters

Data products rarely have one universal contractual context. The same product may be used internally, exposed to partners, or made available through different interfaces with different obligations. Treating the Contract as one unnamed block makes those differences difficult to express and easy to duplicate.

ODPS 4.2 gives these contexts stable names, makes the link from an access interface to its Contract explicit, and allows common profiles to be reused across products. The result is a smaller conceptual change than a new product model, but an important one for operating data products across teams, platforms, and governance boundaries.

ODPS 4.2 is ready for specification users and tool builders. Existing v4.1 documents with singleton Contracts should be migrated and validated against the v4.2 schema before adopting the new version in production workflows.

---

Suggested tags: `Data Products`, `Data Contracts`, `Open Data Product Specification`, `Data Governance`, `Data Mesh`
