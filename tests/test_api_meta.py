"""Method-page and directory API additions. DB-backed tests skip when PostGIS is not reachable."""
import pytest
from fastapi import HTTPException

from sentinel.api.thresholds import thresholds
from sentinel.config import settings
from sentinel.engines.dqr import RULES


def test_fourteen_dqr_rules():
    assert len(RULES) == 14


def test_thresholds_match_settings_and_carry_basis():
    rows = thresholds()
    s = settings()
    assert rows, "no thresholds parsed"
    for r in rows:
        sec = s[r["section"]]
        if r["key"] in sec:
            assert r["value"] == sec[r["key"]]
        else:                                    # nested one level, named "<parent>_<key>" (national.status)
            parent, key = next((p, r["key"][len(p) + 1:]) for p in sec if r["key"].startswith(p + "_") and isinstance(sec[p], dict))
            assert r["value"] == sec[parent][key]
    by = {(r["section"], r["key"]): r for r in rows}
    assert by[("commodity", "min_months")]["basis"] == "POLICY"
    assert by[("service_pressure", "watch_z")]["basis"] == "STAT"
    assert by[("dqr", "missing_fields_major_pct")]["basis"] == "WHO-DQR"
    assert not any(r["section"] in {"simulator", "state", "decision"} for r in rows)


@pytest.fixture(scope="module")
def api():
    """The endpoint module, if PostGIS with loaded marts is reachable. Functions are called directly (no HTTP client)."""
    from sqlalchemy import text

    from sentinel.api import main
    try:
        with main._engine().connect() as c:
            c.execute(text("SELECT 1 FROM mart_lga_month LIMIT 1"))
    except Exception:
        pytest.skip("PostGIS with loaded marts not available")
    return main


def _dir(api, **kw):
    args = dict(state="bauchi", month=None, text_q=None, lga_id=None, queue=None, tag=None, area=None, risk=None,
                confidence=None, stale=False, unverified=False, sort="name", dir="asc", page=1, page_size=25)
    return api.facility_directory(**{**args, **kw})


def test_rules_endpoint_lists_all_fourteen(api):
    ids = [r["rule_id"] for r in api.meta_rules()["rules"]]
    assert sorted(ids) == sorted(RULES)


def test_coords_reports_both_counts(api):
    d = api.state_coords("bauchi")
    assert {"unverified", "outside_state", "near_boundary", "facilities"} <= d.keys()


def test_facilities_paging_filter_and_sort_whitelist(api):
    d = _dir(api, page_size=5, sort="risk", dir="desc")
    assert len(d["facilities"]) == 5 and d["total"] > 5
    act = _dir(api, tag="act now", page_size=1)
    assert 0 < act["total"] < d["total"]
    with pytest.raises(HTTPException) as e:
        _dir(api, sort="name; DROP TABLE x")
    assert e.value.status_code == 422
    everywhere = _dir(api, state=None, page_size=1)       # state=None is the top-bar search across all states
    assert everywhere["total"] > d["total"]


def test_unknown_facility_is_404(api):
    with pytest.raises(HTTPException) as e:
        api.facility("bauchi", "NOPE", None)
    assert e.value.status_code == 404


def test_trend_has_split_and_warmup_flag(api):
    t = api.state_summary("bauchi", None)["trend"]
    assert {"act_now", "verify_then_act", "warmup"} <= t[0].keys()
    assert t[0]["warmup"] is True and t[-1]["warmup"] is False


def test_corroborated_by_names_the_worst_credible_other_domain():
    from sentinel.api.explain import corroborated_by
    ex = {"domains": [
        {"domain": "service_pressure", "label": "Service pressure", "severity": "HIGH", "credible": True, "evidence": []},
        {"domain": "malaria_commodity", "label": "Malaria commodities", "severity": "WATCH", "credible": True, "evidence": [
            {"text": "ACT adult: 40 in stock, so 2.5 months", "mos": 2.5}, {"text": "ACT child: 30 in stock", "mos": 1.84}]},
        {"domain": "vaccine_cold_chain", "label": "Vaccine & cold chain", "severity": "CRITICAL", "credible": False, "evidence": []},
    ]}
    assert corroborated_by(ex, "service_pressure", "HIGH") == "ACT child at 1.8 months (Watch)"
    assert corroborated_by(ex, "service_pressure", "WATCH") is None        # only High or worse
    assert corroborated_by(ex, "malaria_commodity", "HIGH") is None        # only pressure-driven facilities


def test_every_rule_has_a_severity_from_the_engine_source():
    from sentinel.api.thresholds import rule_severities
    sev = rule_severities()
    assert set(sev) == set(RULES) and all(sev.values())
    assert sev["COH_OPD_ZERO"] == ["major"] and sev["COH_SESSIONS"] == ["minor"]
    assert sev["COMP_MISSING_FIELDS"] == ["major", "minor"]


def test_threshold_notes_are_readable_and_calendar_range_is_hidden():
    rows = thresholds()
    keys = {(r["section"], r["key"]) for r in rows}
    assert ("calendar", "first_period") not in keys and ("calendar", "last_period") not in keys
    for r in rows:
        assert "proposal" not in r["note"].lower() and "[" not in r["note"], r
    by = {(r["section"], r["key"]): r for r in rows}
    assert "national min-max inventory policy" in by[("commodity", "min_months")]["note"]
    assert by[("service_pressure", "watch_z")]["note"] == ""      # source not recorded: basis tag only
