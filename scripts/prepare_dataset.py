from pathlib import Path
import csv
import re
from collections import Counter


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "dataset" / "wiki-RfA.txt"

OUTPUT_DIR = PROJECT_ROOT / "dataset" / "processed"

NODES_FILE = OUTPUT_DIR / "nodes.csv"
RELATIONSHIPS_FILE = OUTPUT_DIR / "relationships.csv"


# ============================================================
# Helpers
# ============================================================

def parse_record(lines):
    """
    Parse one wiki-RfA record into a dictionary.

    Expected fields include:
        SRC
        TGT
        VOT
        RES
        YEA
        DAT
        TXT
    """

    record = {}

    for line in lines:
        line = line.rstrip("\n")

        if not line:
            continue

        # TXT can contain ':' so split only once.
        if ":" in line:
            key, value = line.split(":", 1)
            record[key.strip()] = value.strip()

    return record


def clean_user_id(value):
    """
    Normalize user IDs for use as graph node IDs.
    """

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value


# ============================================================
# Main processing
# ============================================================

def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{INPUT_FILE}\n\n"
            "Place wiki-RfA.txt inside the dataset folder."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SNAP wiki-RfA Dataset Preparation")
    print("=" * 60)

    print(f"Input : {INPUT_FILE}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    nodes = set()
    relationships = []

    malformed_records = 0
    total_records = 0

    # --------------------------------------------------------
    # Read dataset
    # --------------------------------------------------------

    current_record = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:

        for raw_line in file:

            line = raw_line.rstrip("\n")

            # Blank line = end of record
            if not line.strip():

                if current_record:

                    total_records += 1

                    record = parse_record(current_record)

                    source = clean_user_id(record.get("SRC"))
                    target = clean_user_id(record.get("TGT"))

                    if source and target:

                        nodes.add(source)
                        nodes.add(target)

                        relationships.append({
                            "source": source,
                            "target": target,
                            "vote": record.get("VOT"),
                            "result": record.get("RES"),
                            "year": record.get("YEA"),
                        })

                    else:
                        malformed_records += 1

                    current_record = []

                continue

            # Ignore comment lines beginning with #
            if line.startswith("#"):
                continue

            current_record.append(line)

    # Handle final record if file doesn't end with blank line
    if current_record:

        total_records += 1

        record = parse_record(current_record)

        source = clean_user_id(record.get("SRC"))
        target = clean_user_id(record.get("TGT"))

        if source and target:

            nodes.add(source)
            nodes.add(target)

            relationships.append({
                "source": source,
                "target": target,
                "vote": record.get("VOT"),
                "result": record.get("RES"),
                "year": record.get("YEA"),
            })

        else:
            malformed_records += 1

    # --------------------------------------------------------
    # Remove exact duplicate relationships
    # --------------------------------------------------------

    unique_relationships = []
    seen_relationships = set()

    for relationship in relationships:

        key = (
            relationship["source"],
            relationship["target"],
            relationship["vote"],
            relationship["year"],
        )

        if key not in seen_relationships:

            seen_relationships.add(key)
            unique_relationships.append(relationship)

    relationships = unique_relationships

    # --------------------------------------------------------
    # Write nodes.csv
    # --------------------------------------------------------

    with NODES_FILE.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=["id"]
        )

        writer.writeheader()

        for node_id in sorted(nodes):

            writer.writerow({
                "id": node_id
            })

    # --------------------------------------------------------
    # Write relationships.csv
    # --------------------------------------------------------

    with RELATIONSHIPS_FILE.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "source",
                "target",
                "vote",
                "result",
                "year"
            ]
        )

        writer.writeheader()

        for relationship in relationships:

            writer.writerow(relationship)

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    vote_counts = Counter(
        relationship["vote"]
        for relationship in relationships
    )

    print()
    print("=" * 60)
    print("DATASET VALIDATION")
    print("=" * 60)

    print(f"Total records parsed       : {total_records:,}")
    print(f"Malformed records          : {malformed_records:,}")
    print(f"Unique nodes               : {len(nodes):,}")
    print(f"Unique relationships       : {len(relationships):,}")

    print()
    print("Vote distribution:")

    for vote, count in sorted(vote_counts.items()):

        print(
            f"  Vote {vote}: {count:,}"
        )

    print()
    print(f"Nodes file        : {NODES_FILE}")
    print(f"Relationships file: {RELATIONSHIPS_FILE}")

    # --------------------------------------------------------
    # Assignment validation
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("ASSIGNMENT CHECK")
    print("=" * 60)

    if len(relationships) >= 100_000:

        print(
            "PASS: Dataset contains at least "
            "100,000 relationships."
        )

    else:

        print(
            "WARNING: Dataset contains fewer than "
            "100,000 relationships."
        )

    print()
    print("Dataset preparation completed successfully.")


if __name__ == "__main__":
    main()