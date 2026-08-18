from __future__ import annotations

import csv
from pathlib import Path

from dotenv import load_dotenv

from benchmark.config import load_database_configs
from benchmark.adapters.cognodb import CognoDBAdapter


PROJECT_ROOT = Path(__file__).resolve().parent.parent

NODES_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "processed"
    / "nodes.csv"
)


def load_user_ids() -> list[str]:
    user_ids = []

    with NODES_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            user_id = (
                row.get("id") or ""
            ).strip()

            if user_id:
                user_ids.append(user_id)

    return user_ids


def inspect_query(
    adapter: CognoDBAdapter,
    name: str,
    query: str,
    **parameters,
) -> None:

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print("Query:")
    print(query.strip())

    print()
    print("Executing PROFILE...")

    profile_query = (
        "PROFILE\n" + query
    )

    try:

        with adapter.driver.session(
            database=adapter.database_name
        ) as session:

            result = session.run(
                profile_query,
                **parameters,
            )

            records = list(result)

            summary = result.consume()

        print()
        print(
            f"Returned records: "
            f"{len(records)}"
        )

        print()
        print("Summary:")

        print(
            f"  Result available: "
            f"{summary.result_available_after}"
        )

        print(
            f"  Result consumed after: "
            f"{summary.result_consumed_after}"
        )

        print()

        if records:

            print("First record:")

            record = records[0]

            try:
                print(
                    record.data()
                )
            except Exception:
                print(
                    record
                )

    except Exception as exc:

        print(
            f"PROFILE failed: "
            f"{type(exc).__name__}: {exc}"
        )


def main() -> int:

    load_dotenv()

    user_ids = load_user_ids()

    if len(user_ids) < 4:
        raise RuntimeError(
            "Not enough User IDs available."
        )

    point_user = user_ids[0]

    indexed_user = user_ids[
        len(user_ids) // 2
    ]

    traversal_user = user_ids[
        len(user_ids) // 4
    ]

    configs = load_database_configs()

    adapter = CognoDBAdapter(
        configs["cognodb"]
    )

    try:

        print("=" * 70)
        print("CognoDB Query Plan Validation")
        print("=" * 70)

        print(
            f"Point lookup user   : "
            f"{point_user}"
        )

        print(
            f"Indexed lookup user : "
            f"{indexed_user}"
        )

        print(
            f"Traversal user      : "
            f"{traversal_user}"
        )

        print()
        print("Connecting to CognoDB...")

        adapter.connect()

        print(
            "Connection established."
        )

        # ----------------------------------------------------
        # Point lookup
        # ----------------------------------------------------

        inspect_query(
            adapter,
            "POINT LOOKUP",
            """
            MATCH (u:User)
            WHERE u.id = $user_id
            RETURN u.id AS id
            LIMIT 1
            """,
            user_id=point_user,
        )

        # ----------------------------------------------------
        # Indexed lookup
        # ----------------------------------------------------

        inspect_query(
            adapter,
            "INDEXED LOOKUP",
            """
            MATCH (u:User {id: $user_id})
            RETURN u.id AS id
            LIMIT 1
            """,
            user_id=indexed_user,
        )

        # ----------------------------------------------------
        # 1-hop traversal
        # ----------------------------------------------------

        inspect_query(
            adapter,
            "1-HOP TRAVERSAL",
            """
            MATCH (start:User {id: $user_id})
            MATCH
                (start)-[:VOTED*1..1]->
                (target:User)
            RETURN DISTINCT target.id AS id
            """,
            user_id=traversal_user,
        )

        # ----------------------------------------------------
        # 3-hop traversal
        # ----------------------------------------------------

        inspect_query(
            adapter,
            "3-HOP TRAVERSAL",
            """
            MATCH (start:User {id: $user_id})
            MATCH
                (start)-[:VOTED*1..3]->
                (target:User)
            RETURN DISTINCT target.id AS id
            """,
            user_id=traversal_user,
        )

        # ----------------------------------------------------
        # Aggregation
        # ----------------------------------------------------

        inspect_query(
            adapter,
            "AGGREGATION",
            """
            MATCH ()-[r:VOTED]->()
            RETURN
                r.vote AS vote,
                count(*) AS relationship_count
            ORDER BY vote
            """,
        )

        print()
        print("=" * 70)
        print("PLAN VALIDATION COMPLETE")
        print("=" * 70)

        return 0

    finally:

        adapter.close()

        print(
            "CognoDB connection closed."
        )


if __name__ == "__main__":
    raise SystemExit(main())