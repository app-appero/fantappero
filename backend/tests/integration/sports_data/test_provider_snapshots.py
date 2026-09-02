"""Integration tests for provider_snapshots idempotency (EP04-01)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sports_data.provider.envelope import parse_envelope
from sports_data.provider.models import ProviderSnapshot
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import ProviderEnvelope, ProviderPaging

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


def test_store_provider_snapshot_idempotent(session: Session) -> None:
    payload = json.loads((DATASET / "reference" / "leagues.json").read_text(encoding="utf-8"))
    envelope = parse_envelope(payload, endpoint="/leagues", http_status=200)

    row1, created1 = store_provider_snapshot(session, envelope)
    session.commit()
    assert created1 is True
    assert row1.payload_hash
    assert row1.endpoint == "/leagues"

    row2, created2 = store_provider_snapshot(session, envelope)
    session.commit()
    assert created2 is False
    assert row2.id == row1.id

    count = session.execute(select(func.count()).select_from(ProviderSnapshot)).scalar_one()
    assert count == 1


def test_changed_payload_creates_new_snapshot_row(session: Session) -> None:
    payload = json.loads((DATASET / "reference" / "leagues.json").read_text(encoding="utf-8"))
    envelope = parse_envelope(payload, endpoint="/leagues", http_status=200)
    store_provider_snapshot(session, envelope)
    session.commit()

    altered = json.loads(json.dumps(payload))
    altered["results"] = 999
    forced = ProviderEnvelope(
        endpoint="/leagues",
        parameters=dict(envelope.parameters),
        errors=[],
        results=999,
        paging=ProviderPaging(current=1, total=1),
        response=list(envelope.response),
        http_status=200,
        raw=altered,
    )
    row2, created2 = store_provider_snapshot(session, forced)
    session.commit()
    assert created2 is True
    count = session.execute(select(func.count()).select_from(ProviderSnapshot)).scalar_one()
    assert count == 2
    assert row2.results_count == 999
