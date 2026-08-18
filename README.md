# CognoDB Graph Database Benchmark

A reproducible benchmark framework for evaluating graph database performance using a common dataset, schema, workload definition, and measurement methodology.

The project currently provides adapters for:

- CognoDB
- Neo4j
- Memgraph
- FalkorDB
- ArangoDB

The benchmark is designed around a common `User` / `VOTED` graph model so that database-specific implementations can be evaluated using equivalent logical operations.

---

## Project Status

| Component | Status |
|---|---|
| Dataset preparation | Complete |
| Common adapter interface | Complete |
| CognoDB adapter | Complete |
| CognoDB dataset loading | Complete |
| CognoDB read benchmark | Complete |
| CognoDB mixed workload | Complete |
| Query validation | Complete |
| Neo4j adapter | Implemented |
| Memgraph adapter | Implemented |
| FalkorDB adapter | Implemented |
| ArangoDB adapter | Implemented |
| Cross-database execution | Pending database instances |
| Final cross-database comparison | Pending |

**Important:** CognoDB is the database for which complete benchmark measurements were executed in the current repository. The other database adapters are implemented, but their benchmark numbers are not fabricated or presented as measured results.

---

## Objective

The goal is to establish a standardized way to measure graph database behavior under the same logical workload.

The benchmark focuses on:

1. Point lookups
2. Indexed lookups
3. 1-hop graph traversal
4. 2-hop graph traversal
5. 3-hop graph traversal
6. Relationship aggregation
7. Mixed 80/20 read/write workloads
8. Increasing client concurrency

The same logical schema and workload definitions are used across database adapters.

---

## Dataset

The benchmark uses the SNAP `wiki-RfA` dataset.

The original raw dataset is intentionally not committed to the repository because it is approximately 50 MB.

The processed benchmark dataset contains:

- **11,377 unique User nodes**
- **193,250 VOTED relationships**

The dataset preparation script also validates malformed records and verifies the minimum relationship requirement.

### Processed files

```text
dataset/
└── processed/
    ├── nodes.csv
    └── relationships.csv
