from __future__ import annotations

from typing import Any, Iterable

from neo4j import GraphDatabase

from .base import GraphDatabaseAdapter, User, VoteRelationship


class CognoDBAdapter(GraphDatabaseAdapter):
    """
    CognoDB adapter using the official Neo4j Python driver.

    Graph schema:

        (:User {
            id
        })

        (:User)-[:VOTED {
            vote,
            result,
            year
        }]->(:User)
    """

    name = "CognoDB"
    database_name = "neo4j"

    NODE_BATCH_SIZE = 1_000
    RELATIONSHIP_BATCH_SIZE = 1_000

    def __init__(self, config):
        super().__init__(config)

        if not config.uri:
            raise ValueError("COGNODB_URI is not configured.")

        if not config.username:
            raise ValueError(
                "COGNODB_USERNAME is not configured."
            )

        if not config.password:
            raise ValueError(
                "COGNODB_PASSWORD is not configured."
            )

        if not config.uri.startswith("bolt+s://"):
            raise ValueError(
                "CognoDB URI must use the bolt+s:// scheme."
            )

        self.driver = None

    # ========================================================
    # CONNECTION
    # ========================================================

    def connect(self) -> None:
        """Connect to CognoDB using the official Neo4j driver."""

        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(
                self.config.username,
                self.config.password,
            ),
        )

        self.driver.verify_connectivity()

    def close(self) -> None:
        """Close the CognoDB driver."""

        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def _require_connection(self) -> None:
        if self.driver is None:
            raise RuntimeError(
                "CognoDB is not connected. "
                "Call connect() first."
            )

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(self) -> bool:
        """Check whether CognoDB is reachable."""

        self._require_connection()

        try:
            with self.driver.session(
                database=self.database_name
            ) as session:

                result = session.run(
                    "RETURN 1 AS health"
                )

                record = result.single()

                return (
                    record is not None
                    and record["health"] == 1
                )

        except Exception:
            return False

    # ========================================================
    # SCHEMA / INDEX
    # ========================================================

    def create_schema(self) -> None:
        """
        Create the User.id lookup index.

        This operation is setup and is not included in
        ingestion timing.
        """

        self._require_connection()

        query = """
        CREATE INDEX user_id_index IF NOT EXISTS
        FOR (u:User)
        ON (u.id)
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(query)
            result.consume()

    # ========================================================
    # CLEAR BENCHMARK DATA
    # ========================================================

    def clear_database(self) -> None:
        """
        Remove only benchmark User nodes and their
        attached VOTED relationships.

        Unrelated labels/data are not intentionally targeted.
        """

        self._require_connection()

        query = """
        MATCH (u:User)
        DETACH DELETE u
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(query)
            result.consume()

    # ========================================================
    # NODE INGESTION
    # ========================================================

    def load_nodes(
        self,
        users: Iterable[User],
    ) -> int:
        """
        Batch-load User nodes.

        The benchmark database is cleared immediately before
        ingestion, and the prepared dataset contains unique
        User IDs, so CREATE is used instead of MERGE.
        """

        self._require_connection()

        users = list(users)

        if not users:
            return 0

        total_loaded = 0

        for start in range(
            0,
            len(users),
            self.NODE_BATCH_SIZE,
        ):

            batch = users[
                start:start + self.NODE_BATCH_SIZE
            ]

            rows = [
                {
                    "id": user.id,
                }
                for user in batch
            ]

            query = """
            UNWIND $rows AS row
            CREATE (u:User {id: row.id})
            """

            with self.driver.session(
                database=self.database_name
            ) as session:

                result = session.run(
                    query,
                    rows=rows,
                )

                result.consume()

            total_loaded += len(batch)

        return total_loaded

    # ========================================================
    # RELATIONSHIP INGESTION
    # ========================================================

    def load_relationships(
        self,
        relationships: Iterable[VoteRelationship],
    ) -> int:
        """
        Batch-load VOTED relationships.
        """

        self._require_connection()

        relationships = list(relationships)

        if not relationships:
            return 0

        total_loaded = 0

        for start in range(
            0,
            len(relationships),
            self.RELATIONSHIP_BATCH_SIZE,
        ):

            batch = relationships[
                start:start + self.RELATIONSHIP_BATCH_SIZE
            ]

            rows = [
                {
                    "source": relationship.source,
                    "target": relationship.target,
                    "vote": self._to_int(
                        relationship.vote
                    ),
                    "result": self._to_int(
                        relationship.result
                    ),
                    "year": self._to_int(
                        relationship.year
                    ),
                }
                for relationship in batch
            ]

            query = """
            UNWIND $rows AS row

            MATCH (source:User {id: row.source})
            MATCH (target:User {id: row.target})

            MERGE (
                source
            )-[r:VOTED {
                vote: row.vote,
                result: row.result,
                year: row.year
            }]->(
                target
            )
            """

            with self.driver.session(
                database=self.database_name
            ) as session:

                result = session.run(
                    query,
                    rows=rows,
                )

                result.consume()

            total_loaded += len(batch)

        return total_loaded

    @staticmethod
    def _to_int(
        value: Any,
    ) -> int | None:
        """Safely convert a value to int."""

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return int(value)

        except ValueError:
            return None

    # ========================================================
    # POINT LOOKUP
    # ========================================================

    def point_lookup(
        self,
        user_id: str,
    ) -> Any:
        """
        Find a User by exact ID.
        """

        self._require_connection()

        query = """
        MATCH (u:User)
        WHERE u.id = $user_id
        RETURN u.id AS id
        LIMIT 1
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(
                query,
                user_id=user_id,
            )

            return result.data()

    # ========================================================
    # INDEXED LOOKUP
    # ========================================================

    def indexed_lookup(
        self,
        user_id: str,
    ) -> Any:
        """
        Find a User using the User.id indexed property.
        """

        self._require_connection()

        query = """
        MATCH (u:User {id: $user_id})
        RETURN u.id AS id
        LIMIT 1
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(
                query,
                user_id=user_id,
            )

            return result.data()

    # ========================================================
    # GRAPH TRAVERSAL
    # ========================================================

    def traverse(
        self,
        user_id: str,
        depth: int,
    ) -> Any:
        """
        Traverse outward from a User.

        Supported depths:
            1
            2
            3
        """

        self._require_connection()

        if depth not in (1, 2, 3):
            raise ValueError(
                "Traversal depth must be 1, 2, or 3."
            )

        query = f"""
        MATCH (start:User {{id: $user_id}})
        MATCH (start)-[:VOTED*1..{depth}]->(target:User)
        RETURN DISTINCT target.id AS id
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(
                query,
                user_id=user_id,
            )

            return result.data()

    # ========================================================
    # AGGREGATION
    # ========================================================

    def aggregation(self) -> Any:
        """
        Count VOTED relationships grouped by vote.
        """

        self._require_connection()

        query = """
        MATCH ()-[r:VOTED]->()

        RETURN
            r.vote AS vote,
            count(*) AS relationship_count

        ORDER BY vote
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(query)

            return result.data()

    # ========================================================
    # MIXED WORKLOAD WRITE
    # ========================================================

    def write_test_record(
        self,
        source_id: str,
        target_id: str,
    ) -> Any:
        """
        Create one temporary benchmark relationship.
        """

        self._require_connection()

        query = """
        MATCH (source:User {id: $source_id})
        MATCH (target:User {id: $target_id})

        CREATE (
            source
        )-[r:VOTED {
            vote: 1,
            result: 1,
            year: 2026
        }]->(
            target
        )
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(
                query,
                source_id=source_id,
                target_id=target_id,
            )

            result.consume()

        return True

    def delete_test_record(
        self,
        source_id: str,
        target_id: str,
    ) -> Any:
        """
        Delete temporary benchmark relationships created
        with year=2026.
        """

        self._require_connection()

        query = """
        MATCH (
            source:User {id: $source_id}
        )-[r:VOTED {
            year: 2026
        }]->(
            target:User {id: $target_id}
        )

        DELETE r
        """

        with self.driver.session(
            database=self.database_name
        ) as session:

            result = session.run(
                query,
                source_id=source_id,
                target_id=target_id,
            )

            result.consume()

        return True

    # ========================================================
    # RESOURCE INFORMATION
    # ========================================================

    def get_resource_usage(
        self,
    ) -> dict[str, Any]:
        """
        Return observable resource information.

        The benchmark adapter does not currently expose
        host-level CPU, memory or storage metrics.
        """

        return {
            "cpu": "not observable",
            "memory": "not observable",
            "storage": "not observable",
        }