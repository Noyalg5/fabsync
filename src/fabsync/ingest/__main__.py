"""Command-line entry point: ``python -m fabsync.ingest`` loads data/raw into the warehouse."""

from fabsync.ingest.pipeline import main

if __name__ == "__main__":
    main()
