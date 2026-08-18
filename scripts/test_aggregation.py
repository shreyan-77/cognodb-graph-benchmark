from dotenv import load_dotenv

from benchmark.config import load_database_configs
from benchmark.adapters.cognodb import CognoDBAdapter


def main():
    load_dotenv()

    configs = load_database_configs()
    adapter = CognoDBAdapter(configs["cognodb"])

    try:
        print("Connecting to CognoDB...")

        adapter.connect()

        print("Connection established.")

        if not adapter.health_check():
            raise RuntimeError("Health check failed.")

        print("Running one aggregation...")

        records = adapter.aggregation()

        print("Aggregation completed.")

        print(f"Returned groups: {len(records)}")

        for record in records:
            print(record)

    finally:
        adapter.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()