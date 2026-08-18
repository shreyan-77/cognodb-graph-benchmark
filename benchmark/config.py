from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BenchmarkConfig:
    # Reproducibility
    random_seed: int = 42

    # Read benchmark
    warmup_iterations: int = 20
    measured_iterations: int = 100

    # Mixed workload
    concurrency_levels: tuple[int, ...] = (1, 10, 40)
    read_ratio: float = 0.80
    write_ratio: float = 0.20
    mixed_duration_seconds: int = 60

    # Dataset
    nodes_file: str = "dataset/processed/nodes.csv"
    relationships_file: str = "dataset/processed/relationships.csv"

    # Graph model
    node_label: str = "User"
    relationship_type: str = "VOTED"
    node_id_property: str = "id"

    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        return cls(
            random_seed=int(os.getenv("BENCHMARK_SEED", "42")),
            warmup_iterations=int(
                os.getenv("BENCHMARK_WARMUP_ITERATIONS", "20")
            ),
            measured_iterations=int(
                os.getenv("BENCHMARK_ITERATIONS", "100")
            ),
            mixed_duration_seconds=int(
                os.getenv("MIXED_DURATION_SECONDS", "60")
            ),
        )


@dataclass(frozen=True)
class DatabaseConfig:
    name: str
    uri: str | None
    username: str | None
    password: str | None


def load_database_configs() -> dict[str, DatabaseConfig]:
    return {
        "cognodb": DatabaseConfig(
            name="CognoDB",
            uri=os.getenv("COGNODB_URI"),
            username=os.getenv("COGNODB_USERNAME", "cognodb"),
            password=os.getenv("COGNODB_PASSWORD"),
        ),

        "neo4j": DatabaseConfig(
            name="Neo4j",
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
        ),

        "memgraph": DatabaseConfig(
            name="Memgraph",
            uri=os.getenv("MEMGRAPH_URI"),
            username=os.getenv("MEMGRAPH_USERNAME"),
            password=os.getenv("MEMGRAPH_PASSWORD"),
        ),

        "falkordb": DatabaseConfig(
            name="FalkorDB",
            uri=os.getenv("FALKORDB_URI"),
            username=os.getenv("FALKORDB_USERNAME"),
            password=os.getenv("FALKORDB_PASSWORD"),
        ),

        "arangodb": DatabaseConfig(
            name="ArangoDB",
            uri=os.getenv("ARANGODB_URI"),
            username=os.getenv("ARANGODB_USERNAME"),
            password=os.getenv("ARANGODB_PASSWORD"),
        ),
    }