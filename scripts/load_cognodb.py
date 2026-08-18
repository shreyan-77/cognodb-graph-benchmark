from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from benchmark.config import load_database_configs
from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.adapters.base import User, VoteRelationship


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NODES_FILE = PROJECT_ROOT / "dataset" / "processed" / "nodes.csv"
RELATIONSHIPS_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "processed"
    / "relationships.csv"
)


# ============================================================
# Helpers
# ============================================================

def load_users() -> list[User]:
    """Read User nodes from nodes.csv."""

    if not NODES_FILE.exists():
        raise FileNotFoundError(
            f"Nodes file not found:\n{NODES_FILE}"
        )

    users: list[User] = []

    with NODES_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if "id" not in (reader.fieldnames or []):
            raise ValueError(
                "nodes.csv must contain an 'id' column."
            )

        for row in reader:

            user_id = (row.get("id") or "").strip()

            if user_id:
                users.append(
                    User(id=user_id)
                )

    return users


def load_relationships() -> list[VoteRelationship]:
    """Read VOTED relationships from relationships.csv."""

    if not RELATIONSHIPS_FILE.exists():
        raise FileNotFoundError(
            f"Relationships file not found:\n"
            f"{RELATIONSHIPS_FILE}"
        )

    relationships: list[VoteRelationship] = []

    with RELATIONSHIPS_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "source",
            "target",
            "vote",
            "result",
            "year",
        }

        actual_columns = set(
            reader.fieldnames or []
        )

        missing = required_columns - actual_columns

        if missing:
            raise ValueError(
                "relationships.csv is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:

            source = (row.get("source") or "").strip()
            target = (row.get("target") or "").strip()

            if not source or not target:
                continue

            relationships.append(
                VoteRelationship(
                    source=source,
                    target=target,
                    vote=parse_int(row.get("vote")),
                    result=parse_int(row.get("result")),
                    year=parse_int(row.get("year")),
                )
            )

    return relationships


def parse_int(value: str | None) -> int | None:
    """Safely convert CSV values to integers."""

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def verify_counts(adapter: CognoDBAdapter) -> tuple[int, int]:
    """
    Verify final User and VOTED counts in CognoDB.

    Returns:
        (node_count, relationship_count)
    """

    adapter._require_connection()

    query = """
    MATCH (u:User)
    WITH count(u) AS node_count

    OPTIONAL MATCH ()-[r:VOTED]->()

    RETURN
        node_count,
        count(r) AS relationship_count
    """

    result = adapter.driver.execute_query(
        query,
        database_=adapter.database_name,
    )

    if not result.records:
        raise RuntimeError(
            "CognoDB returned no verification result."
        )

    record = result.records[0]

    return (
        record["node_count"],
        record["relationship_count"],
    )


# ============================================================
# Main
# ============================================================

def main() -> int:

    load_dotenv()

    print("=" * 70)
    print("CognoDB Dataset Loader")
    print("=" * 70)

    print(f"Nodes file        : {NODES_FILE}")
    print(f"Relationships file: {RELATIONSHIPS_FILE}")
    print()

    # --------------------------------------------------------
    # Load local CSV files first.
    # This is NOT database benchmark time.
    # --------------------------------------------------------

    print("Reading dataset...")

    users = load_users()
    relationships = load_relationships()

    print(f"Users loaded from CSV         : {len(users):,}")
    print(
        f"Relationships loaded from CSV: "
        f"{len(relationships):,}"
    )

    if len(users) == 0:
        raise RuntimeError(
            "nodes.csv contains no users."
        )

    if len(relationships) == 0:
        raise RuntimeError(
            "relationships.csv contains no relationships."
        )

    print()

    # --------------------------------------------------------
    # Load configuration.
    # --------------------------------------------------------

    configs = load_database_configs()

    adapter = CognoDBAdapter(
        configs["cognodb"]
    )

    try:

        # ====================================================
        # SETUP
        # ====================================================

        print("=" * 70)
        print("SETUP")
        print("=" * 70)

        setup_start = time.perf_counter()

        print("Connecting to CognoDB...")

        adapter.connect()

        print("Connection established.")

        print("Running health check...")

        if not adapter.health_check():
            raise RuntimeError(
                "CognoDB health check failed."
            )

        print("Health check: PASS")

        # ----------------------------------------------------
        # Clear benchmark data only.
        #
        # Our benchmark database is dedicated to this
        # experiment, so all User/VOTED benchmark data can
        # safely be removed.
        # ----------------------------------------------------

        print("Clearing existing benchmark data...")

        adapter.clear_database()

        print("Benchmark data cleared.")

        # ----------------------------------------------------
        # Create schema/index.
        # ----------------------------------------------------

        print("Creating User.id index...")

        adapter.create_schema()

        print("User.id index ready.")

        setup_elapsed = (
            time.perf_counter() - setup_start
        )

        print(
            f"Setup time (not ingestion): "
            f"{setup_elapsed:.3f} seconds"
        )

        print()

        # ====================================================
        # NODE INGESTION
        # ====================================================

        print("=" * 70)
        print("NODE INGESTION")
        print("=" * 70)

        node_start = time.perf_counter()

        loaded_nodes = adapter.load_nodes(users)

        node_elapsed = (
            time.perf_counter() - node_start
        )

        node_rate = (
            loaded_nodes / node_elapsed
            if node_elapsed > 0
            else 0
        )

        print(
            f"Nodes submitted : {loaded_nodes:,}"
        )

        print(
            f"Node load time  : {node_elapsed:.3f} seconds"
        )

        print(
            f"Node throughput : {node_rate:,.2f} nodes/sec"
        )

        print()

        # ====================================================
        # RELATIONSHIP INGESTION
        # ====================================================

        print("=" * 70)
        print("RELATIONSHIP INGESTION")
        print("=" * 70)

        relationship_start = time.perf_counter()

        loaded_relationships = (
            adapter.load_relationships(
                relationships
            )
        )

        relationship_elapsed = (
            time.perf_counter()
            - relationship_start
        )

        relationship_rate = (
            loaded_relationships
            / relationship_elapsed
            if relationship_elapsed > 0
            else 0
        )

        print(
            f"Relationships submitted : "
            f"{loaded_relationships:,}"
        )

        print(
            f"Relationship load time  : "
            f"{relationship_elapsed:.3f} seconds"
        )

        print(
            f"Relationship throughput : "
            f"{relationship_rate:,.2f} relationships/sec"
        )

        print()

        # ====================================================
        # VERIFICATION
        # ====================================================

        print("=" * 70)
        print("FINAL VERIFICATION")
        print("=" * 70)

        actual_nodes, actual_relationships = (
            verify_counts(adapter)
        )

        print(
            f"Expected nodes        : {len(users):,}"
        )

        print(
            f"Actual nodes          : {actual_nodes:,}"
        )

        print(
            f"Expected relationships: "
            f"{len(relationships):,}"
        )

        print(
            f"Actual relationships  : "
            f"{actual_relationships:,}"
        )

        nodes_match = (
            actual_nodes == len(users)
        )

        relationships_match = (
            actual_relationships
            == len(relationships)
        )

        print()

        print(
            "Node count check      : "
            f"{'PASS' if nodes_match else 'FAIL'}"
        )

        print(
            "Relationship count check: "
            f"{'PASS' if relationships_match else 'FAIL'}"
        )

        if not nodes_match or not relationships_match:

            raise RuntimeError(
                "Final database counts do not match "
                "the prepared dataset."
            )

        # ====================================================
        # SUMMARY
        # ====================================================

        print()
        print("=" * 70)
        print("COGNODB LOAD SUMMARY")
        print("=" * 70)

        print(
            f"Nodes                  : {actual_nodes:,}"
        )

        print(
            f"Relationships           : "
            f"{actual_relationships:,}"
        )

        print(
            f"Node ingestion time     : "
            f"{node_elapsed:.3f} sec"
        )

        print(
            f"Relationship ingestion  : "
            f"{relationship_elapsed:.3f} sec"
        )

        print(
            f"Node throughput         : "
            f"{node_rate:,.2f} nodes/sec"
        )

        print(
            f"Relationship throughput : "
            f"{relationship_rate:,.2f} rel/sec"
        )

        print()
        print("CognoDB dataset load: PASS")

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("LOAD FAILED")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1

    finally:

        adapter.close()

        print()
        print("CognoDB connection closed.")


if __name__ == "__main__":
    sys.exit(main())