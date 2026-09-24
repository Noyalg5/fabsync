"""Smoke test: the package imports."""

import fabsync


def test_package_imports() -> None:
    assert fabsync.__version__
