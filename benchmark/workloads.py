from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadRequest:
    name: str
    description: str


WORKLOADS = {
    "point_lookup": WorkloadRequest(
        name="point_lookup",
        description="Find a User by exact ID.",
    ),

    "indexed_lookup": WorkloadRequest(
        name="indexed_lookup",
        description="Find a User using the indexed id property.",
    ),

    "traversal_1hop": WorkloadRequest(
        name="traversal_1hop",
        description="Find users one relationship away from a start User.",
    ),

    "traversal_2hop": WorkloadRequest(
        name="traversal_2hop",
        description="Find users within two relationship hops.",
    ),

    "traversal_3hop": WorkloadRequest(
        name="traversal_3hop",
        description="Find users within three relationship hops.",
    ),

    "aggregation": WorkloadRequest(
        name="aggregation",
        description="Aggregate relationships by vote.",
    ),

    "write": WorkloadRequest(
        name="write",
        description="Create a benchmark write operation.",
    ),
}


TRAVERSAL_DEPTHS = (1, 2, 3)