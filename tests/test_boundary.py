"""Boundary tagging: ok / Near boundary (mapped) / Location unverified (queued, not mapped)."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sentinel import config
from sentinel.facility import grid3

NEAR_KM = config.settings()["geography"]["near_boundary_km"]


@pytest.mark.parametrize("inside,dist,expected", [
    (True, 0, "ok"),
    (False, 1, "near_boundary"),
    (False, NEAR_KM * 1000, "near_boundary"),          # exactly at the threshold
    (False, NEAR_KM * 1000 + 1, "location_unverified"),
    (False, 80_000, "location_unverified"),
])
def test_coord_status_threshold(inside, dist, expected):
    assert grid3.coord_status(inside, dist, NEAR_KM) == expected


def test_threshold_comes_from_config():
    assert grid3.coord_status(False, 7000, 10) == "near_boundary"
    assert grid3.coord_status(False, 7000, 5) == "location_unverified"


def _facility(uid, name, lat, lon, lga="Alpha"):
    return {"type": "Feature", "geometry": None, "properties": {
        "unique_id": uid, "latitude": lat, "longitude": lon, "state_standard": "Test", "lga_standard": lga,
        "ward_standard": "W1", "facility_name": name, "facility_level": "Primary", "facility_type": "PHC",
        "facility_ownership": "Public", "facility_ownership_type": "LGA", "functional": "Functional",
        "nhfr_facility_code": "", "issues": "", "flag_count": 0}}


def test_build_tags_points_and_keeps_all_facilities(tmp_path, monkeypatch):
    """One 1-degree square LGA; points inside, ~2 km outside and ~20 km outside."""
    square = {"type": "Polygon", "coordinates": [[[8, 10], [9, 10], [9, 11], [8, 11], [8, 10]]]}
    lga = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": square, "properties": {"lganame": "Alpha", "lgacode": "99001", "statename": "Test"}}]}
    fac = {"type": "FeatureCollection", "features": [
        _facility("T1", "Inside PHC", 10.5, 8.5),
        _facility("T2", "Edge PHC", 10.5, 9.018),     # ~2 km east of the polygon
        _facility("T3", "Far PHC", 10.5, 9.18),       # ~20 km east
        _facility("T4", "Primary private", 10.5, 8.4) | {},
    ]}
    fac["features"][3]["properties"]["facility_ownership"] = "Private"   # filtered out
    (tmp_path / "f.geojson").write_text(json.dumps(fac))
    (tmp_path / "l.geojson").write_text(json.dumps(lga))
    st = {"code": "test", "name": "Test", "zone": "North East", "grid3_code": "TS", "lga_aliases": {}}
    monkeypatch.setattr(grid3, "raw_paths", lambda code: (tmp_path / "f.geojson", tmp_path / "l.geojson"))
    monkeypatch.setattr(grid3, "state_cfg", lambda code: st)
    monkeypatch.setattr(config, "STATES_DIR", tmp_path / "states")

    dim = grid3.build("test").set_index("facility_id")
    assert list(dim.index.sort_values()) == ["T1", "T2", "T3"]          # private dropped; none dropped for location
    assert dim.loc["T1", "coord_status"] == "ok"
    assert dim.loc["T2", "coord_status"] == "near_boundary"
    assert dim.loc["T3", "coord_status"] == "location_unverified"
    assert not dim.loc["T3", "in_state"]
    assert (dim["state_code"] == "test").all() and dim["lmis_facility_code"].str.startswith("TS-LMIS-").all()
    log = json.loads((tmp_path / "states" / "test" / "logs" / "facility_master.json").read_text())
    assert log["coord_location_unverified"] == 1 and log["coord_near_boundary"] == 1


def test_unmatched_lga_names_the_fix(tmp_path, monkeypatch):
    square = {"type": "Polygon", "coordinates": [[[8, 10], [9, 10], [9, 11], [8, 11], [8, 10]]]}
    lga = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": square, "properties": {"lganame": "Garun Malam", "lgacode": "1", "statename": "T"}}]}
    fac = {"type": "FeatureCollection", "features": [_facility("A", "PHC", 10.5, 8.5, lga="Garum Mallam")]}
    (tmp_path / "f.geojson").write_text(json.dumps(fac))
    (tmp_path / "l.geojson").write_text(json.dumps(lga))
    st = {"code": "t", "name": "T", "zone": "x", "grid3_code": "TT", "lga_aliases": {}}
    monkeypatch.setattr(grid3, "raw_paths", lambda code: (tmp_path / "f.geojson", tmp_path / "l.geojson"))
    monkeypatch.setattr(grid3, "state_cfg", lambda code: st)
    monkeypatch.setattr(config, "STATES_DIR", tmp_path / "states")
    with pytest.raises(ValueError, match="lga_aliases"):
        grid3.build("t")
    st["lga_aliases"] = {"garummallam": "garunmalam"}
    assert grid3.build("t")["lga"].iloc[0] == "Garun Malam"


def test_real_states_have_no_unmatched_or_dropped_locations():
    """Every built state keeps every public primary facility with coordinates, whatever its tag."""
    for code in config.state_codes():
        log_path = config.StatePaths(code).logs / "facility_master.json"
        if not log_path.exists():
            pytest.skip("facility masters not built")
        log = json.loads(log_path.read_text())
        tagged = sum(v for k, v in log.items() if k.startswith("coord_"))
        assert tagged == log["facilities_loaded"], code
        dim = pd.read_parquet(config.StatePaths(code).staging / "dim_facility.parquet")
        assert set(dim["coord_status"]) <= {"ok", "near_boundary", "location_unverified"}
