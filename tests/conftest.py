"""Shared pytest fixtures."""

from datetime import datetime, timezone

import pytest

from src.common.types import Event, Trace


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
