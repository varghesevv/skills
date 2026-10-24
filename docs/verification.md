# Verification rules

Skills is a closed, high-trust community that spans several churches. Nobody joins by signing up alone: every person is vouched for by people already known to the church, and a verifier gives the final sign-off.

Agreed with the product owner on 2026-10-24.

## Context

- Expected scale: about 10,000 users, of whom at least 4,000 are providers.
- Churches do not keep a formal membership roll, so verification cannot rely on one. Trust comes from people who know each other instead.

## Roles

| Role | What they do |
|---|---|
| **Minister** | Leads a church and appoints its vouchers. |
| **Voucher** | Appointed by the minister: a home group leader, or a senior person the minister knows personally. |
| **Verifier** | Reviews the vouches for an applicant and gives the final sign-off that admits them. |
| **Searcher** | Finds providers for work they need doing. |
| **Provider** | Lists their skills and services. |

Each church has its own verifiers, vouchers, providers and searchers.

## What each applicant needs

| Applicant | Vouches needed | Then |
|---|---|---|
| **Searcher** | 1 vouch from anyone already in the system | Verifier signs off |
| **Provider** | At least 2 vouches: 1 from an appointed voucher (for example a home group leader) and 1 from an existing searcher | Verifier signs off |

A searcher has a lighter check than a provider, because a provider is the role others rely on for work.

## Why this design

- It mirrors how a church already works: the minister knows the senior people and home group leaders, and they know their groups.
- Every admitted person has a chain of trust that leads back to the minister.
- Requiring an appointed voucher for every provider keeps the higher-trust role tied to church leadership, while the second vouch from a searcher adds an independent witness.

## Relation to the current specification

The [specification](specification/README.md) still describes organisations vouching for freelancers. These rules replace that model at the product level; the specification, data model and API need updating to match before the rules are built.
