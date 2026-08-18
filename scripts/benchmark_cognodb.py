from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.config import load_database_configs


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NODES_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "processed"
    / "nodes.csv"
)

RESULTS_DIR = PROJECT_ROOT / "results"

RESULTS_FILE = (
    RESULTS_DIR / "cognodb_benchmark.json"
)


# ============================================================
# BENCHMARK CONFIGURATION
# ============================================================

WARMUP_ITERATIONS = 20

STANDARD_MEASURED_ITERATIONS = 100

AGGREGATION_MEASURED_ITERATIONS = 10

RANDOM_SEED = 42


# ============================================================
# DATASET
# ============================================================

def load_user_ids() -> list[str]:
    """
    Load User IDs from the prepared nodes.csv file.

    The same deterministic dataset is used across databases.
    """

    if not NODES_FILE.exists():
        raise FileNotFoundError(
            f"Nodes file not found:\n{NODES_FILE}"
        )

    user_ids: list[str] = []

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

            user_id = (
                row.get("id") or ""
            ).strip()

            if user_id:
                user_ids.append(user_id)

    if not user_ids:
        raise RuntimeError(
            "No User IDs were found in nodes.csv."
        )

    return user_ids


# ============================================================
# STATISTICS
# ============================================================

def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    """
    Calculate a percentile using linear interpolation.
    """

    if not values:
        raise ValueError(
            "Cannot calculate percentile from empty data."
        )

    ordered = sorted(values)

    position = (
        len(ordered) - 1
    ) * percentile_value

    lower = int(position)

    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = position - lower

    return (
        ordered[lower]
        + fraction
        * (
            ordered[upper]
            - ordered[lower]
        )
    )


def calculate_statistics(
    latencies_ms: list[float],
) -> dict:

    if not latencies_ms:
        raise ValueError(
            "No latency measurements available."
        )

    return {
        "iterations": len(latencies_ms),
        "p50_ms": percentile(
            latencies_ms,
            0.50,
        ),
        "p95_ms": percentile(
            latencies_ms,
            0.95,
        ),
        "mean_ms": statistics.mean(
            latencies_ms
        ),
        "min_ms": min(
            latencies_ms
        ),
        "max_ms": max(
            latencies_ms
        ),
    }


# ============================================================
# TIMING
# ============================================================

def measure_operation(
    operation,
    iterations: int,
) -> list[float]:
    """
    Execute an operation repeatedly.

    Returned latency values are milliseconds.
    """

    latencies_ms: list[float] = []

    for _ in range(iterations):

        start = time.perf_counter()

        operation()

        elapsed = (
            time.perf_counter()
            - start
        )

        latencies_ms.append(
            elapsed * 1000
        )

    return latencies_ms


# ============================================================
# RESULT STORAGE
# ============================================================

def create_workload_result(
    name: str,
    warmup_iterations: int,
    measured_iterations: int,
    latencies_ms: list[float],
) -> dict:

    statistics_result = calculate_statistics(
        latencies_ms
    )

    return {
        "workload": name,
        "warmup_iterations": warmup_iterations,
        "measured_iterations": measured_iterations,
        "statistics": statistics_result,
        "latencies_ms": latencies_ms,
    }


def save_results(
    results: dict,
) -> None:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RESULTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
        )


# ============================================================
# TERMINAL REPORT
# ============================================================

def print_result(
    name: str,
    result: dict,
) -> None:

    stats = result["statistics"]

    print()
    print("-" * 70)
    print(name)
    print("-" * 70)

    print(
        f"Warm-up    : "
        f"{result['warmup_iterations']}"
    )

    print(
        f"Iterations : "
        f"{stats['iterations']}"
    )

    print(
        f"p50        : "
        f"{stats['p50_ms']:.3f} ms"
    )

    print(
        f"p95        : "
        f"{stats['p95_ms']:.3f} ms"
    )

    print(
        f"Mean       : "
        f"{stats['mean_ms']:.3f} ms"
    )

    print(
        f"Min        : "
        f"{stats['min_ms']:.3f} ms"
    )

    print(
        f"Max        : "
        f"{stats['max_ms']:.3f} ms"
    )


# ============================================================
# BENCHMARK
# ============================================================

def run_benchmark(
    adapter: CognoDBAdapter,
    user_ids: list[str],
) -> dict:

    # --------------------------------------------------------
    # Deterministic User IDs
    # --------------------------------------------------------

    point_user = user_ids[0]

    indexed_user = user_ids[
        len(user_ids) // 2
    ]

    traversal_user = user_ids[
        len(user_ids) // 4
    ]

    print()
    print("=" * 70)
    print("BENCHMARK CONFIGURATION")
    print("=" * 70)

    print(
        f"Warm-up iterations       : "
        f"{WARMUP_ITERATIONS}"
    )

    print(
        f"Standard measurements    : "
        f"{STANDARD_MEASURED_ITERATIONS}"
    )

    print(
        f"Aggregation measurements : "
        f"{AGGREGATION_MEASURED_ITERATIONS}"
    )

    print(
        f"Random seed              : "
        f"{RANDOM_SEED}"
    )

    print(
        f"Point lookup User        : "
        f"{point_user}"
    )

    print(
        f"Indexed lookup User      : "
        f"{indexed_user}"
    )

    print(
        f"Traversal User           : "
        f"{traversal_user}"
    )

    workloads: dict[str, dict] = {}

    # ========================================================
    # POINT LOOKUP
    # ========================================================

    print()
    print("=" * 70)
    print("POINT LOOKUP")
    print("=" * 70)

    print("Running warm-up...")

    measure_operation(
        lambda: adapter.point_lookup(
            point_user
        ),
        WARMUP_ITERATIONS,
    )

    print("Running measured iterations...")

    latencies = measure_operation(
        lambda: adapter.point_lookup(
            point_user
        ),
        STANDARD_MEASURED_ITERATIONS,
    )

    workloads["point_lookup"] = create_workload_result(
        "Point Lookup",
        WARMUP_ITERATIONS,
        STANDARD_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "Point Lookup",
        workloads["point_lookup"],
    )

    # ========================================================
    # INDEXED LOOKUP
    # ========================================================

    print()
    print("=" * 70)
    print("INDEXED LOOKUP")
    print("=" * 70)

    print("Running warm-up...")

    measure_operation(
        lambda: adapter.indexed_lookup(
            indexed_user
        ),
        WARMUP_ITERATIONS,
    )

    print("Running measured iterations...")

    latencies = measure_operation(
        lambda: adapter.indexed_lookup(
            indexed_user
        ),
        STANDARD_MEASURED_ITERATIONS,
    )

    workloads["indexed_lookup"] = create_workload_result(
        "Indexed Lookup",
        WARMUP_ITERATIONS,
        STANDARD_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "Indexed Lookup",
        workloads["indexed_lookup"],
    )

    # ========================================================
    # 1-HOP TRAVERSAL
    # ========================================================

    print()
    print("=" * 70)
    print("1-HOP TRAVERSAL")
    print("=" * 70)

    print("Running warm-up...")

    measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            1,
        ),
        WARMUP_ITERATIONS,
    )

    print("Running measured iterations...")

    latencies = measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            1,
        ),
        STANDARD_MEASURED_ITERATIONS,
    )

    workloads["traversal_1_hop"] = create_workload_result(
        "1-Hop Traversal",
        WARMUP_ITERATIONS,
        STANDARD_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "1-Hop Traversal",
        workloads["traversal_1_hop"],
    )

    # ========================================================
    # 2-HOP TRAVERSAL
    # ========================================================

    print()
    print("=" * 70)
    print("2-HOP TRAVERSAL")
    print("=" * 70)

    print("Running warm-up...")

    measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            2,
        ),
        WARMUP_ITERATIONS,
    )

    print("Running measured iterations...")

    latencies = measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            2,
        ),
        STANDARD_MEASURED_ITERATIONS,
    )

    workloads["traversal_2_hop"] = create_workload_result(
        "2-Hop Traversal",
        WARMUP_ITERATIONS,
        STANDARD_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "2-Hop Traversal",
        workloads["traversal_2_hop"],
    )

    # ========================================================
    # 3-HOP TRAVERSAL
    # ========================================================

    print()
    print("=" * 70)
    print("3-HOP TRAVERSAL")
    print("=" * 70)

    print("Running warm-up...")

    measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            3,
        ),
        WARMUP_ITERATIONS,
    )

    print("Running measured iterations...")

    latencies = measure_operation(
        lambda: adapter.traverse(
            traversal_user,
            3,
        ),
        STANDARD_MEASURED_ITERATIONS,
    )

    workloads["traversal_3_hop"] = create_workload_result(
        "3-Hop Traversal",
        WARMUP_ITERATIONS,
        STANDARD_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "3-Hop Traversal",
        workloads["traversal_3_hop"],
    )

    # ========================================================
    # AGGREGATION
    # ========================================================

    print()
    print("=" * 70)
    print("AGGREGATION")
    print("=" * 70)

    print(
        f"Running {WARMUP_ITERATIONS} warm-up iterations..."
    )

    measure_operation(
        lambda: adapter.aggregation(),
        WARMUP_ITERATIONS,
    )

    print(
        f"Running {AGGREGATION_MEASURED_ITERATIONS} "
        f"measured iterations..."
    )

    latencies = measure_operation(
        lambda: adapter.aggregation(),
        AGGREGATION_MEASURED_ITERATIONS,
    )

    workloads["aggregation"] = create_workload_result(
        "Aggregation",
        WARMUP_ITERATIONS,
        AGGREGATION_MEASURED_ITERATIONS,
        latencies,
    )

    print_result(
        "Aggregation",
        workloads["aggregation"],
    )

    return workloads


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    load_dotenv()

    print("=" * 70)
    print("CognoDB Benchmark")
    print("=" * 70)

    try:

        # ----------------------------------------------------
        # Load dataset IDs
        # ----------------------------------------------------

        user_ids = load_user_ids()

        print(
            f"Loaded {len(user_ids):,} User IDs."
        )

        # ----------------------------------------------------
        # Load database configuration
        # ----------------------------------------------------

        configs = load_database_configs()

        adapter = CognoDBAdapter(
            configs["cognodb"]
        )

        try:

            # ------------------------------------------------
            # Connect
            # ------------------------------------------------

            print(
                "Connecting to CognoDB..."
            )

            adapter.connect()

            print(
                "Connection established."
            )

            # ------------------------------------------------
            # Health check
            # ------------------------------------------------

            if not adapter.health_check():
                raise RuntimeError(
                    "CognoDB health check failed."
                )

            print(
                "Health check: PASS"
            )

            # ------------------------------------------------
            # Run benchmark
            # ------------------------------------------------

            workloads = run_benchmark(
                adapter,
                user_ids,
            )

        finally:

            adapter.close()

            print()
            print(
                "CognoDB connection closed."
            )

        # ====================================================
        # BUILD MACHINE-READABLE RESULT
        # ====================================================

        results = {
            "benchmark": {
                "database": "CognoDB",
                "dataset": "SNAP wiki-RfA",
                "node_count": 11377,
                "relationship_count": 193250,
                "warmup_iterations": WARMUP_ITERATIONS,
                "standard_measured_iterations": (
                    STANDARD_MEASURED_ITERATIONS
                ),
                "aggregation_measured_iterations": (
                    AGGREGATION_MEASURED_ITERATIONS
                ),
                "random_seed": RANDOM_SEED,
                "timestamp_utc": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            },
            "workloads": workloads,
        }

        # ----------------------------------------------------
        # Save JSON
        # ----------------------------------------------------

        save_results(results)

        print()
        print("=" * 70)
        print("RESULTS SAVED")
        print("=" * 70)

        print(
            f"File: {RESULTS_FILE}"
        )

        print()
        print("=" * 70)
        print("BENCHMARK COMPLETE")
        print("=" * 70)

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("BENCHMARK FAILED")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())