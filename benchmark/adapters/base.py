from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class User:
    id: str


@dataclass(frozen=True)
class VoteRelationship:
    source: str
    target: str
    vote: int | None
    result: int | None
    year: int | None


class GraphDatabaseAdapter(ABC):
    """
    Common interface for every graph database.

    All database-specific implementations must provide the same
    logical operations so that the benchmark runner can remain
    database-agnostic.
    """

    name: str

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def connect(self) -> None:
        """Open a database connection."""

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def health_check(self) -> bool:
        """Verify that the database is reachable."""

    @abstractmethod
    def clear_database(self) -> None:
        """Remove benchmark data before a fresh load."""

    @abstractmethod
    def create_schema(self) -> None:
        """
        Create the User.id lookup index / equivalent schema.
        """

    @abstractmethod
    def load_nodes(self, users: Iterable[User]) -> int:
        """
        Load User nodes.

        Returns:
            Number of nodes successfully submitted/loaded.
        """

    @abstractmethod
    def load_relationships(
        self,
        relationships: Iterable[VoteRelationship],
    ) -> int:
        """
        Load VOTED relationships.

        Returns:
            Number of relationships successfully submitted/loaded.
        """

    @abstractmethod
    def point_lookup(self, user_id: str) -> Any:
        """Find one User by ID."""

    @abstractmethod
    def indexed_lookup(self, user_id: str) -> Any:
        """
        Execute the indexed/equivalent User.id lookup.
        """

    @abstractmethod
    def traverse(self, user_id: str, depth: int) -> Any:
        """
        Traverse the graph from a User to the requested depth.

        depth must be 1, 2, or 3.
        """

    @abstractmethod
    def aggregation(self) -> Any:
        """
        Run the standardized aggregation workload.
        """

    @abstractmethod
    def write_test_record(self, source_id: str, target_id: str) -> Any:
        """
        Execute one standardized write operation.
        """

    @abstractmethod
    def delete_test_record(
        self,
        source_id: str,
        target_id: str,
    ) -> Any:
        """
        Remove a benchmark write record if necessary.
        """

    @abstractmethod
    def get_resource_usage(self) -> dict[str, Any]:
        """
        Return observable resource information.

        If the platform does not expose a metric, use:
            {"memory": "not observable"}
        rather than estimating it.
        """