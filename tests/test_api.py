"""API: state-parameterised endpoints and the national endpoints, against the loaded database.
Skipped when PostgreSQL is not reachable (unit tests do not need it)."""
from __future__ import annotations

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from sentinel import config  # noqa: E402


@pytest.fixture(scope="module")
def client():
    from sqlalchemy import text

    from sentinel.api.main import app
    from sentinel.db import engine
    try:
        with engine().connect() as c:
            if not c.execute(text("SELECT to_regclass('mart_national_month')")).scalar():
                pytest.skip("national marts not loaded")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"database not reachable: {e}")
    return TestClient(app)


def test_every_state_summary(client):
    for code in config.state_codes():
        r = client.get(f"/state/{code}/summary", params={"month": "2026-09"})
        assert r.status_code == 200, code
        d = r.json()
        assert d["state"]["code"] == code
        k = d["kpis"]
        assert k["act_now"] + k["verify_then_act"] + k["verification"] + k["monitor"] == k["facilities"]
        assert sum(l["facilities"] for l in d["lgas"]) == k["facilities"]
        assert sum(m["n"] for m in d["matrix"]) == k["facilities"]


def test_unknown_state_is_404(client):
    assert client.get("/state/lagos/summary").status_code == 404


def test_bauchi_through_state_and_legacy_paths(client):
    a = client.get("/state/bauchi/summary", params={"month": "2026-09"}).json()["kpis"]
    b = client.get("/state/summary", params={"month": "2026-09"}).json()["kpis"]
    assert a == b
    assert (a["act_now"], a["verify_then_act"], a["verification"], a["monitor"]) == (188, 72, 581, 613)


def test_national_summary_reconciles_with_states(client):
    nat = client.get("/national/summary", params={"month": "2026-09"}).json()
    sts = client.get("/national/states", params={"month": "2026-09"}).json()["states"]
    assert len(sts) == 12 and nat["kpis"]["states"] == 12
    for key in ("facilities", "act_now", "verify_then_act", "verification", "monitor", "stale_commodity", "reports_received"):
        assert nat["kpis"][key] == sum(s[key] for s in sts), key
    for z in nat["zones"]:
        assert z["facilities"] == sum(s["facilities"] for s in sts if s["zone"] == z["zone"])


def test_national_states_brief_payload(client):
    d = client.get("/national/states", params={"metric": "pct_verification"}).json()
    s = d["states"][0]
    assert d["metric"] == "pct_verification" and s["value"] == s["pct_verification"]
    assert len(s["trend"]) == config.settings()["national"]["trend_months"]
    assert 1 <= len(s["top_lgas"]) <= config.settings()["national"]["top_lgas_in_brief"]
    assert sorted(x["metric_rank"] for x in d["states"]) == list(range(1, 13))
    assert client.get("/national/states", params={"metric": "nonsense"}).status_code == 422


def test_national_payload_is_small(client):
    r = client.get("/national/states", headers={"Accept-Encoding": "gzip"})
    assert len(r.content) < 60_000          # state aggregates only, no facility rows
    assert "facility_id" not in r.text


def test_facility_scoped_to_its_state(client):
    q = client.get("/state/kano/top").json()["action"][0]
    assert client.get(f"/state/kano/facility/{q['facility_id']}").status_code == 200
    assert client.get(f"/state/bauchi/facility/{q['facility_id']}").status_code == 404


def test_location_unverified_not_mapped(client):
    feats = client.get("/state/niger/geo/facilities").json()["features"]
    assert feats and all(f["properties"]["coord_status"] != "location_unverified" for f in feats)
