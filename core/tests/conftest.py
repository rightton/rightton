"""Shared helpers. Every expected value in this suite is worked out by hand in the
test itself (the arithmetic is written in the comment or as plain numbers), never
taken from the code under test."""

import sys
from pathlib import Path

import pytest

# Make the package importable without installing it, from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def approx(value, rel=1e-4, abs_=1e-9):
    return pytest.approx(value, rel=rel, abs=abs_)
