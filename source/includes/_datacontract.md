# Data Contract

The OPTIONAL `product.contract` object declares the formal data contracts that govern a data product. ODPS 4.2 supports reusable, named Data Contract profiles. New implementations SHOULD use the profile form so that Data Access interfaces can state which contractual context applies.

When contract profiles are defined inline, a profile named `default` is REQUIRED. One or more additional profiles may be added with names chosen by the publisher. Each profile uses the existing Contract object; ODPS does not define a second contract model.

> Example of named Data Contract profiles:

```yaml
schema: https://opendataproducts.org/v4.2/schema/odps.yaml
version: 4.2
product:
  contract:
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

An individual Contract profile can be defined in three ways:

* use `$ref` to load the individual contract definition from a local or external file;
* provide `id`, `type`, `contractVersion`, and `contractURL` metadata that links to a contract management system; or
* provide the metadata and embed contract content under `spec`.

> Example of external and inline individual profiles:

```yaml
contract:
  default:
    $ref: https://example.org/contracts/default.yaml
  internal:
    id: CONTRACT-002
    type: ODCS
    contractVersion: 2.2.2
    spec:
      apiVersion: v2.2.2
      kind: DataContract
```

The complete profile collection may instead be maintained as an external package. The referenced file represents the profile collection itself and MUST contain `default`.

```yaml
contract:
  $ref: https://example.org/contracts/contract-profiles.yaml
```

These two reference locations have different meanings:

* `product.contract.$ref` references an external package containing multiple named profiles.
* `product.contract.<profile>.$ref` references the external definition of one specific profile.

The same contract profile MAY be referenced by several Data Access profiles. This enables define-once, reference-many governance without copying a complete Contract object into each access definition.

Complete examples are available for [named profiles](examples/DataContract/contract-profiles.yml), [Data Access bindings](examples/DataContract/contract-access-reference.yml), [an external individual profile](examples/DataContract/contract-external-profile.yml), [inline contract content](examples/DataContract/datacontract-inline.yml), and [an external profile package](examples/DataContract/contract-profiles-package.yml).

### Legacy singleton compatibility

The ODPS 4.1 singleton form remains valid in ODPS 4.2 for backward compatibility:

```yaml
contract:
  id: CONTRACT-001
  type: ODCS
  contractVersion: 2.2.2
  contractURL: https://example.org/contracts/default
```

The singleton metadata, inline `spec`, and external `$ref` forms remain accepted. A legacy singleton `$ref` and a v4.2 external profile-package `$ref` have the same wrapper shape; tools that resolve external content determine whether the target is one Contract or a profile collection. For new documents, a `$ref` directly under `product.contract` SHOULD target a profile package.

The singleton form is deprecated for new implementations because it cannot express several reusable contractual contexts or explicit Data Access-to-contract relationships. Existing documents do not need to migrate unless they need those capabilities.

## Optional attributes and elements

| <div style="width:150px">Element name</div> | Type | Options | Description |
|---|---|---|---|
| **contract** | object | legacy Contract, named profiles, or package `$ref` | OPTIONAL collection of Data Contract profiles. Inline profile collections MUST contain `default`. The legacy singleton Contract remains valid for compatibility. |
| **default** | Contract | - | REQUIRED only when the named profile form is used inline. It is the primary contractual context. |
| **&lt;profile&gt;** | Contract | publisher-defined name | An additional reusable contractual context, such as `internal` or `restricted`. |
| **id** | string | - | Identifier of an individual data contract. |
| **type** | string | ODCS, DCS | Standard used by the individual contract. Supported options are [ODCS](https://github.com/bitol-io/open-data-contract-standard) and [DCS](https://datacontract.com/). |
| **contractVersion** | string | - | Version of the standard used to define the Data Contract, not the revision of the contract instance itself. |
| **contractURL** | URL | Valid URL; see [RFC 3986](https://datatracker.ietf.org/doc/html/rfc3986) | Location of the individual contract in a contract management service or similar system. |
| **spec** | object | YAML object | Inline content for an individual contract profile. |
| **$ref** | URI reference | local or external | At `product.contract`, references a complete profile package. At a named profile, references one individual contract definition. |
