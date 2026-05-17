"""Smoke tests: import the package and confirm version is well-formed."""

from __future__ import annotations

import re

import gannon_analysis


def test_version_is_semver() -> None:
    assert re.match(r"^\d+\.\d+\.\d+", gannon_analysis.__version__)


def test_package_imports_clean() -> None:
    assert hasattr(gannon_analysis, "__version__")
