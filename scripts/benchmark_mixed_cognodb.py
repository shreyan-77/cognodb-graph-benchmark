from __future__ import annotations

import csv
import json
import random
import statistics
import sys
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.config import load_database_configs


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

USER_IDS_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "processed"
    / "nodes.csv"
)

RESULTS_DIR = PROJECT_ROOT / "results"

RESULTS_FILE = (
    RESULTS_DIR
    / "cognodb_mixed_benchmark.json"
)


# ============================================================
# BENCHMARK CONFIGURATION
# ============================================================

CONCURRENCY_LEVELS = [
    1,
    5,
    10,
    20,
    40,
]

WARMUP_OPERATIONS_PER_CLIENT = 20

MEASURED_OPERATIONS_PER_CLIENT = 200

READ_RATIO = 0.80
WRITE_RATIO = 0.20

RANDOM_SEED = 42


# ============================================================
# DATASET
# ============================================================

def load_user_ids() -> list[str]:
    """Load User IDs from the prepared dataset."""

    user_ids: list[str] = []

    with USER_IDS_FILE.open(
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

    if len(user_ids) < 2:
        raise RuntimeError(
            "At least two User IDs are required."
        )

    return user_ids


# ============================================================
# STATISTICS
# ============================================================

def percentile(
    values: list[float],
    percentile_value: float,
) -> float:

    if not values:
        return 0.0

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
    latencies: list[float],
) -> dict:

    if not latencies:

        return {
            "iterations": 0,
            "p50_ms": None,
            "p95_ms": None,
            "mean_ms": None,
            "min_ms": None,
            "max_ms": None,
        }

    return {
        "iterations": len(latencies),
        "p50_ms": percentile(
            latencies,
            0.50,
        ),
        "p95_ms": percentile(
            latencies,
            0.95,
        ),
        "mean_ms": statistics.mean(
            latencies
        ),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
    }


# ============================================================
# RESULT FILE
# ============================================================

def save_partial_results(
    results: dict,
) -> None:
    """
    Save results immediately.

    This is deliberately called after every concurrency
    level so completed results survive a later failure.
    """

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
# CONNECTION SETUP
# ============================================================

def establish_clients(
    concurrency: int,
    config,
) -> tuple[
    list[CognoDBAdapter],
    list[dict],
]:
    """
    Establish and verify all requested client connections
    before the workload timer starts.

    Returns:

        clients
        connection_failures
    """

    clients: list[CognoDBAdapter] = []

    connection_failures: list[dict] = []

    print()
    print(
        f"Establishing {concurrency} "
        f"CognoDB client connections..."
    )

    for client_id in range(concurrency):

        adapter = CognoDBAdapter(config)

        connection_start = (
            time.perf_counter()
        )

        try:

            adapter.connect()

            if not adapter.health_check():
                raise RuntimeError(
                    "Health check failed."
                )

            connection_elapsed = (
                time.perf_counter()
                - connection_start
            )

            clients.append(adapter)

            print(
                f"  Client {client_id + 1:02d}: "
                f"READY "
                f"({connection_elapsed:.3f}s)"
            )

        except Exception as exc:

            connection_elapsed = (
                time.perf_counter()
                - connection_start
            )

            print(
                f"  Client {client_id + 1:02d}: "
                f"FAILED "
                f"({connection_elapsed:.3f}s)"
            )

            connection_failures.append(
                {
                    "client_id": client_id,
                    "error_type": (
                        type(exc).__name__
                    ),
                    "error": str(exc),
                    "elapsed_seconds": (
                        connection_elapsed
                    ),
                }
            )

            try:
                adapter.close()
            except Exception:
                pass

    return (
        clients,
        connection_failures,
    )


def close_clients(
    clients: list[CognoDBAdapter],
) -> None:

    for adapter in clients:

        try:
            adapter.close()
        except Exception:
            pass


# ============================================================
# OPERATION EXECUTION
# ============================================================

def execute_read(
    adapter: CognoDBAdapter,
    user_ids: list[str],
    rng: random.Random,
) -> None:

    user_id = rng.choice(
        user_ids
    )

    choice = rng.random()

    if choice < 0.40:

        adapter.indexed_lookup(
            user_id
        )

    elif choice < 0.70:

        adapter.point_lookup(
            user_id
        )

    elif choice < 0.90:

        adapter.traverse(
            user_id,
            1,
        )

    else:

        adapter.traverse(
            user_id,
            2,
        )


def execute_write(
    adapter: CognoDBAdapter,
    user_ids: list[str],
    client_id: int,
    operation_index: int,
) -> None:

    source_index = (
        client_id * 2
        + operation_index
    ) % len(user_ids)

    target_index = (
        source_index + 1
    ) % len(user_ids)

    source_id = user_ids[
        source_index
    ]

    target_id = user_ids[
        target_index
    ]

    if source_id == target_id:

        target_index = (
            target_index + 1
        ) % len(user_ids)

        target_id = user_ids[
            target_index
        ]

    adapter.write_test_record(
        source_id,
        target_id,
    )

    try:

        # The write is complete at this point.
        # Cleanup happens immediately so the benchmark
        # dataset is not permanently modified.

        pass

    finally:

        adapter.delete_test_record(
            source_id,
            target_id,
        )


def execute_operation(
    adapter: CognoDBAdapter,
    user_ids: list[str],
    rng: random.Random,
    operation_type: str,
    client_id: int,
    operation_index: int,
) -> None:

    if operation_type == "read":

        execute_read(
            adapter,
            user_ids,
            rng,
        )

    else:

        execute_write(
            adapter,
            user_ids,
            client_id,
            operation_index,
        )


# ============================================================
# SINGLE CLIENT WORKER
# ============================================================

def run_client(
    client_id: int,
    adapter: CognoDBAdapter,
    user_ids: list[str],
    measured_operations: int,
) -> dict:
    """
    Run one client using an already-established connection.

    Connection establishment is deliberately outside this
    function's workload timing.
    """

    rng = random.Random(
        RANDOM_SEED + client_id
    )

    latencies_ms: list[float] = []

    read_count = 0
    write_count = 0

    errors = 0
    warmup_errors = 0

    # --------------------------------------------------------
    # Warm-up
    # --------------------------------------------------------

    for warmup_index in range(
        WARMUP_OPERATIONS_PER_CLIENT
    ):

        operation_type = (
            "read"
            if rng.random() < READ_RATIO
            else "write"
        )

        try:

            execute_operation(
                adapter,
                user_ids,
                rng,
                operation_type,
                client_id,
                warmup_index,
            )

        except Exception:

            warmup_errors += 1

    # --------------------------------------------------------
    # Measured operations
    # --------------------------------------------------------

    for operation_index in range(
        measured_operations
    ):

        operation_type = (
            "read"
            if rng.random() < READ_RATIO
            else "write"
        )

        start = time.perf_counter()

        try:

            execute_operation(
                adapter,
                user_ids,
                rng,
                operation_type,
                client_id,
                operation_index,
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            latencies_ms.append(
                elapsed * 1000
            )

            if operation_type == "read":
                read_count += 1
            else:
                write_count += 1

        except Exception:

            errors += 1

    return {
        "client_id": client_id,
        "read_operations": read_count,
        "write_operations": write_count,
        "successful_operations": len(
            latencies_ms
        ),
        "errors": errors,
        "warmup_errors": warmup_errors,
        "latencies_ms": latencies_ms,
    }


# ============================================================
# CONCURRENCY LEVEL
# ============================================================

def run_concurrency_level(
    concurrency: int,
    config,
    user_ids: list[str],
) -> dict:

    print()
    print("=" * 70)
    print(
        f"CONCURRENCY: {concurrency}"
    )
    print("=" * 70)

    total_expected = (
        concurrency
        * MEASURED_OPERATIONS_PER_CLIENT
    )

    # --------------------------------------------------------
    # Establish ALL connections first.
    # --------------------------------------------------------

    clients, connection_failures = (
        establish_clients(
            concurrency,
            config,
        )
    )

    # --------------------------------------------------------
    # If we could not establish every requested client,
    # do NOT run a partial concurrency test.
    # --------------------------------------------------------

    if len(clients) != concurrency:

        close_clients(clients)

        print()
        print(
            f"CONNECTION SETUP FAILED: "
            f"{len(clients)}/{concurrency} "
            f"clients ready."
        )

        return {
            "concurrency": concurrency,
            "status": "connection_failed",

            "clients_requested": concurrency,

            "clients_ready": len(clients),

            "connection_failures": (
                connection_failures
            ),

            "operations_per_client": (
                MEASURED_OPERATIONS_PER_CLIENT
            ),

            "expected_operations": (
                total_expected
            ),

            "total_operations": 0,

            "successful_operations": 0,

            "read_operations": 0,

            "write_operations": 0,

            "errors": 0,

            "warmup_errors": 0,

            "elapsed_seconds": None,

            "throughput_ops_per_sec": None,

            "actual_read_ratio": None,

            "actual_write_ratio": None,

            "latency": (
                calculate_statistics([])
            ),

            "latencies_ms": [],
        }

    # --------------------------------------------------------
    # All connections are ready.
    #
    # Start timing ONLY NOW.
    # --------------------------------------------------------

    print()
    print(
        "All client connections verified."
    )

    print(
        "Starting measured workload..."
    )

    all_latencies: list[float] = []

    total_reads = 0
    total_writes = 0
    total_errors = 0
    total_warmup_errors = 0

    workload_start = (
        time.perf_counter()
    )

    try:

        with ThreadPoolExecutor(
            max_workers=concurrency
        ) as executor:

            futures = []

            for client_id, adapter in enumerate(
                clients
            ):

                futures.append(
                    executor.submit(
                        run_client,
                        client_id,
                        adapter,
                        user_ids,
                        MEASURED_OPERATIONS_PER_CLIENT,
                    )
                )

            for future in as_completed(
                futures
            ):

                result = future.result()

                all_latencies.extend(
                    result["latencies_ms"]
                )

                total_reads += (
                    result["read_operations"]
                )

                total_writes += (
                    result["write_operations"]
                )

                total_errors += (
                    result["errors"]
                )

                total_warmup_errors += (
                    result["warmup_errors"]
                )

    finally:

        workload_elapsed = (
            time.perf_counter()
            - workload_start
        )

        close_clients(clients)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    successful_operations = len(
        all_latencies
    )

    total_operations = (
        total_reads
        + total_writes
        + total_errors
    )

    throughput = (
        successful_operations
        / workload_elapsed
        if workload_elapsed > 0
        else 0.0
    )

    result = {
        "concurrency": concurrency,
        "status": "completed",

        "clients_requested": concurrency,

        "clients_ready": len(clients),

        "connection_failures": (
            connection_failures
        ),

        "operations_per_client": (
            MEASURED_OPERATIONS_PER_CLIENT
        ),

        "expected_operations": (
            total_expected
        ),

        "total_operations": (
            total_operations
        ),

        "successful_operations": (
            successful_operations
        ),

        "read_operations": total_reads,

        "write_operations": total_writes,

        "errors": total_errors,

        "warmup_errors": (
            total_warmup_errors
        ),

        "elapsed_seconds": (
            workload_elapsed
        ),

        "throughput_ops_per_sec": (
            throughput
        ),

        "actual_read_ratio": (
            total_reads / total_operations
            if total_operations
            else 0.0
        ),

        "actual_write_ratio": (
            total_writes / total_operations
            if total_operations
            else 0.0
        ),

        "latency": calculate_statistics(
            all_latencies
        ),

        "latencies_ms": all_latencies,
    }

    # --------------------------------------------------------
    # Terminal report
    # --------------------------------------------------------

    print()
    print(
        f"Total operations : "
        f"{total_operations}"
    )

    print(
        f"Successful       : "
        f"{successful_operations}"
    )

    print(
        f"Reads            : "
        f"{total_reads}"
    )

    print(
        f"Writes           : "
        f"{total_writes}"
    )

    print(
        f"Errors            : "
        f"{total_errors}"
    )

    print(
        f"Elapsed           : "
        f"{workload_elapsed:.3f} sec"
    )

    print(
        f"Throughput        : "
        f"{throughput:.2f} ops/sec"
    )

    latency = result["latency"]

    print(
        f"p50               : "
        f"{latency['p50_ms']:.3f} ms"
    )

    print(
        f"p95               : "
        f"{latency['p95_ms']:.3f} ms"
    )

    print(
        f"Mean              : "
        f"{latency['mean_ms']:.3f} ms"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    load_dotenv()

    print("=" * 70)
    print(
        "CognoDB 80/20 Mixed Read/Write Benchmark"
    )
    print("=" * 70)

    try:

        # ----------------------------------------------------
        # Dataset
        # ----------------------------------------------------

        user_ids = load_user_ids()

        print(
            f"Loaded {len(user_ids):,} User IDs."
        )

        # ----------------------------------------------------
        # Configuration
        # ----------------------------------------------------

        configs = (
            load_database_configs()
        )

        config = configs["cognodb"]

        benchmark_start = (
            time.perf_counter()
        )

        results = {
            "benchmark": {
                "database": "CognoDB",

                "workload": (
                    "80/20 mixed read/write"
                ),

                "dataset": "SNAP wiki-RfA",

                "node_count": 11377,

                "relationship_count": 193250,

                "concurrency_levels": (
                    CONCURRENCY_LEVELS
                ),

                "warmup_operations_per_client": (
                    WARMUP_OPERATIONS_PER_CLIENT
                ),

                "measured_operations_per_client": (
                    MEASURED_OPERATIONS_PER_CLIENT
                ),

                "read_ratio_target": READ_RATIO,

                "write_ratio_target": WRITE_RATIO,

                "random_seed": RANDOM_SEED,

                "timestamp_utc": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            },

            "results": [],
        }

        # ----------------------------------------------------
        # Run every requested concurrency level.
        #
        # Results are saved immediately after each level.
        # ----------------------------------------------------

        for concurrency in CONCURRENCY_LEVELS:

            try:

                result = run_concurrency_level(
                    concurrency,
                    config,
                    user_ids,
                )

                results["results"].append(
                    result
                )

                # Save immediately.
                save_partial_results(
                    results
                )

                print()
                print(
                    "Partial results saved."
                )

                # ------------------------------------------------
                # If connection setup failed, continue to the
                # next requested concurrency level.
                # ------------------------------------------------

                if (
                    result["status"]
                    == "connection_failed"
                ):

                    print()
                    print(
                        "This concurrency level "
                        "could not be established."
                    )

                    print(
                        "Continuing to the "
                        "next level..."
                    )

            except Exception as exc:

                # ------------------------------------------------
                # Preserve everything completed so far.
                # ------------------------------------------------

                failure_result = {
                    "concurrency": concurrency,
                    "status": "benchmark_failed",

                    "error_type": (
                        type(exc).__name__
                    ),

                    "error": str(exc),
                }

                results["results"].append(
                    failure_result
                )

                save_partial_results(
                    results
                )

                print()
                print(
                    f"Concurrency {concurrency} "
                    f"failed:"
                )

                print(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                print(
                    "Partial results saved."
                )

                # Continue to the next level.
                continue

        # ----------------------------------------------------
        # Final metadata
        # ----------------------------------------------------

        results["benchmark"][
            "benchmark_elapsed_seconds"
        ] = (
            time.perf_counter()
            - benchmark_start
        )

        results["benchmark"][
            "completed_at_utc"
        ] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        save_partial_results(
            results
        )

        # ----------------------------------------------------
        # Final summary
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print(
            "MIXED BENCHMARK COMPLETE"
        )
        print("=" * 70)

        print(
            f"Results saved to:\n"
            f"{RESULTS_FILE}"
        )

        completed = sum(
            1
            for item in results["results"]
            if item.get("status")
            == "completed"
        )

        connection_failed = sum(
            1
            for item in results["results"]
            if item.get("status")
            == "connection_failed"
        )

        benchmark_failed = sum(
            1
            for item in results["results"]
            if item.get("status")
            == "benchmark_failed"
        )

        print()
        print(
            f"Completed levels       : "
            f"{completed}"
        )

        print(
            f"Connection failures    : "
            f"{connection_failed}"
        )

        print(
            f"Benchmark failures     : "
            f"{benchmark_failed}"
        )

        return 0

    except KeyboardInterrupt:

        print()
        print(
            "Benchmark interrupted by user."
        )

        print(
            "Any previously saved partial "
            "results remain in:"
        )

        print(
            RESULTS_FILE
        )

        return 130

    except Exception as exc:

        print()
        print("=" * 70)
        print(
            "MIXED BENCHMARK FAILED"
        )
        print("=" * 70)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())