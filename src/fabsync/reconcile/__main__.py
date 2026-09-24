"""Command-line entry point: ``python -m fabsync.reconcile`` runs the four reconciliation engines."""

from fabsync.reconcile.pipeline import main

if __name__ == "__main__":
    main()
