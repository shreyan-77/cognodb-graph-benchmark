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

        healthy = adapter.health_check()

        print(f"Health check: {'PASS' if healthy else 'FAIL'}")

        if not healthy:
            raise RuntimeError(
                "CognoDB health check failed."
            )

        print("Creating User.id index...")

        adapter.create_schema()

        print("Schema/index setup complete.")

    finally:
        adapter.close()

        print("Connection closed.")


if __name__ == "__main__":
    main()