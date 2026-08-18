from dataclasses import dataclass
from statistics import mean, median
from typing import Sequence


@dataclass(frozen=True)
class LatencyResult:
    workload: str
    database: str
    iterations: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float


def percentile(values: Sequence[float], percentile_value: float) -> float:
    if not values:
        raise ValueError("Cannot calculate percentile from empty data.")

    sorted_values = sorted(values)

    rank = (len(sorted_values) - 1) * percentile_value

    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)

    weight = rank - lower

    return (
        sorted_values[lower]
        + weight * (sorted_values[upper] - sorted_values[lower])
    )


def calculate_latency(
    database: str,
    workload: str,
    latencies_ms: Sequence[float],
) -> LatencyResult:

    if not latencies_ms:
        raise ValueError("No latency measurements supplied.")

    return LatencyResult(
        workload=workload,
        database=database,
        iterations=len(latencies_ms),
        p50_ms=percentile(latencies_ms, 0.50),
        p95_ms=percentile(latencies_ms, 0.95),
        mean_ms=mean(latencies_ms),
        min_ms=min(latencies_ms),
        max_ms=max(latencies_ms),
    )