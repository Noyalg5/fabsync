"""Command-line entry point for synthetic source generation.

Delegates to fabsync.ingest.generate_sources so that ``make generate`` and
``python -m fabsync.generate`` do the same thing.
"""

from fabsync.ingest.generate_sources import main

if __name__ == "__main__":
    main()
