"""Shared pytest fixtures."""

import os

# Ensure unit tests use SQLite in-memory database per Doc 08 §3
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402

from src.common.types import Event, Trace  # noqa: E402


@pytest.fixture
def sample_event():
    return Event(
        case_id="case-001",
        activity="OrderCreated",
        timestamp=datetime.now(timezone.utc),
        attributes={"amount": 100.0},
    )


@pytest.fixture
def sample_trace(sample_event):
    return Trace(
        case_id="case-001",
        events=[sample_event],
    )
