"""Phase 1: facility master and LGA geography from GRID3 (real, public data), per state.

fetch(code)        downloads one state's raw layers into data/raw/grid3 (committed, so builds are offline).
fetch_states_geo() downloads the national state boundaries used by the National Command Centre map.
coverage()         Step-1 check: facility and LGA-boundary coverage in GRID3 for each configured state.
build(code)        filters to public primary facilities, standardises, de-duplicates and
                   validates each coordinate against its LGA polygon.
"""
from __future__ import annotations

import hashlib
import json
import re
import string

import pandas as pd
import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from ..config import RAW_DIR, StatePaths, settings
from ..config import state as state_cfg
from ..config import states as all_states

ARCGIS = "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services"
FACILITY_LAYER = "GRID3_NGA_health_facility_v3_0"
LGA_LAYER = "NGA_LGA_Boundaries_2"
STATE_LAYER = "NGA_State_Boundaries_V2"
GRID3_DIR = RAW_DIR / "grid3"
STATES_GEO = GRID3_DIR / "nga_state_boundaries.geojson"

FACILITY_FIELDS = [
    "unique_id", "latitude", "longitude", "state_standard", "lga_standard", "ward_standard",
    "facility_name", "facility_level", "facility_type", "facility_ownership",
    "facility_ownership_type", "functional", "nhfr_facility_code", "issues", "flag_count",
]


def _query_geojson(layer: str, where: str, out_fields: str, page: int = 1000, order: str | None = None, **extra) -> dict:
    features, offset = [], 0
    while True:
        params = {
            "where": where, "outFields": out_fields, "f": "geojson",
            "orderByFields": order or ("OBJECTID" if layer == FACILITY_LAYER else "FID"),
            "resultOffset": offset, "resultRecordCount": page, **extra,
        }
        r = requests.get(f"{ARCGIS}/{layer}/FeatureServer/0/query", params=params, timeout=120)
        r.raise_for_status()
        batch = r.json().get("features", [])
        features.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return {"type": "FeatureCollection", "features": features}


def raw_paths(code: str) -> tuple:
    return GRID3_DIR / f"{code}_health_facilities_v3.geojson", GRID3_DIR / f"{code}_lga_boundaries.geojson"


def fetch(code: str) -> None:
    st = state_cfg(code)
    GRID3_DIR.mkdir(parents=True, exist_ok=True)
    fac_path, lga_path = raw_paths(code)
    fac = _query_geojson(FACILITY_LAYER, f"state_standard='{st['grid3_facility_state']}'", ",".join(FACILITY_FIELDS))
    fac_path.write_text(json.dumps(fac), encoding="utf-8")
    lga = _query_geojson(LGA_LAYER, f"statename='{st['grid3_boundary_state']}'", "lganame,lgacode,statename",
                         page=100, geometryPrecision=5)
    lga_path.write_text(json.dumps(lga), encoding="utf-8")
    print(f"GRID3 {st['name']}: {len(fac['features'])} facilities, {len(lga['features'])} LGA polygons")


def fetch_states_geo(tolerance: float = 0.01) -> None:
    """All 36 states + FCT, simplified for a national map (~0.01 degree, about 1 km)."""
    meta = requests.get(f"{ARCGIS}/{STATE_LAYER}/FeatureServer/0", params={"f": "json"}, timeout=60).json()
    oid = next((f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeOID"), "FID")
    fc = _query_geojson(STATE_LAYER, "1=1", "*", page=100, order=oid, geometryPrecision=4, maxAllowableOffset=tolerance)
    feats = []
    for f in fc["features"]:
        p = {k.lower(): v for k, v in f["properties"].items()}
        feats.append({"type": "Feature", "geometry": f["geometry"],
                      "properties": {"name": p.get("statename"), "grid3_code": p.get("statecode")}})
    GRID3_DIR.mkdir(parents=True, exist_ok=True)
    STATES_GEO.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    print(f"GRID3 state boundaries: {len(feats)} states -> {STATES_GEO}")


def coverage() -> list[dict]:
    """Step-1 check: facility and LGA-boundary coverage in GRID3 for every configured state."""
    def count(layer, where):
        r = requests.get(f"{ARCGIS}/{layer}/FeatureServer/0/query",
                         params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=120)
        r.raise_for_status()
        return r.json().get("count", 0)
    return [{"code": st["code"], "state": st["name"], "zone": st["zone"],
             "facilities_v3": count(FACILITY_LAYER, f"state_standard='{st['grid3_facility_state']}'"),
             "lga_polygons": count(LGA_LAYER, f"statename='{st['grid3_boundary_state']}'")}
            for st in all_states()]


def norm_key(s: str, aliases: dict | None = None) -> str:
    """Normalised LGA / facility-name key. `aliases` maps facility-layer LGA spellings
    to boundary-layer spellings (per state, in settings.yaml)."""
    k = re.sub(r"[^a-z0-9]", "", str(s).lower())
    return (aliases or {}).get(k, k)


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def synthetic_uid(seed: str) -> str:
    """Deterministic 11-character DHIS2-style UID (first char a letter)."""
    alphabet = string.ascii_letters + string.digits
    h = hashlib.sha256(seed.encode()).digest()
    return string.ascii_letters[h[0] % 52] + "".join(alphabet[b % 62] for b in h[1:11])


def coord_status(inside: bool, dist_m: float, near_km: float) -> str:
    """ok: inside its own LGA polygon. near_boundary: outside, but within `near_km` of it
    (boundary precision; drawn on the map). location_unverified: further away (kept in
    every queue, not drawn on the map)."""
    if inside:
        return "ok"
    return "near_boundary" if dist_m <= near_km * 1000 else "location_unverified"


def _lmis_codes(ids: pd.Series, prefix: str) -> pd.Series:
    """Synthetic LMIS facility codes: PREFIX-LMIS-<hash>. Six hex characters, lengthened
    for the whole state only if two facilities would collide."""
    for n in range(6, 33):
        codes = ids.map(lambda u: f"{prefix}-LMIS-" + hashlib.md5(u.encode()).hexdigest()[:n].upper())
        if codes.is_unique:
            return codes
    raise ValueError("duplicate facility ids")


def _haversine_m(lat1, lon1, lat2, lon2):
    import numpy as np
    r = 6_371_000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def build(code: str) -> pd.DataFrame:
    st = state_cfg(code)
    state = st["name"]
    aliases = st["lga_aliases"]
    near_km = settings()["geography"]["near_boundary_km"]
    paths = StatePaths(code).ensure()
    fac_path, lga_path = raw_paths(code)
    fac = pd.DataFrame([f["properties"] for f in json.loads(fac_path.read_text(encoding="utf-8"))["features"]])
    lga_fc = json.loads(lga_path.read_text(encoding="utf-8"))
    log: dict[str, int] = {"raw_records": len(fac)}

    fac = fac[(fac["facility_level"] == "Primary") & (fac["facility_ownership"] == "Public")].copy()
    log["public_primary"] = len(fac)

    fac["facility_name"] = fac["facility_name"].map(clean_name)
    fac["lga"] = fac["lga_standard"].map(clean_name)
    fac["ward"] = fac["ward_standard"].fillna("").map(clean_name)
    n = len(fac)
    fac = fac.dropna(subset=["latitude", "longitude"])
    log["missing_coordinates_dropped"] = n - len(fac)
    n = len(fac)
    fac = fac.drop_duplicates("unique_id")
    log["duplicate_ids_dropped"] = n - len(fac)

    # De-duplicate: same normalised name in the same LGA within 100 m; keep the record with fewer GRID3 flags.
    fac["name_key"] = fac["facility_name"].map(norm_key)
    fac["flag_count"] = fac["flag_count"].fillna(0)
    fac = fac.sort_values(["flag_count", "unique_id"])
    keep = []
    for _, grp in fac.groupby(["lga", "name_key"], sort=False):
        kept: list = []
        for idx, row in grp.iterrows():
            if any(_haversine_m(row.latitude, row.longitude, fac.at[k, "latitude"], fac.at[k, "longitude"]) < 100 for k in kept):
                continue
            kept.append(idx)
        keep.extend(kept)
    log["near_duplicates_removed"] = len(fac) - len(keep)
    fac = fac.loc[keep]

    # Validate each coordinate against its own LGA polygon (and the state as a whole).
    lgas = {norm_key(f["properties"]["lganame"]): f for f in lga_fc["features"]}
    unmatched = sorted(set(fac["lga"].map(lambda x: norm_key(x, aliases))) - set(lgas))
    if unmatched:
        raise ValueError(f"{state}: facility LGAs with no boundary polygon: {unmatched}; "
                         f"add them to lga_aliases in settings.yaml (boundary names: {sorted(lgas)})")
    polys = {k: shape(f["geometry"]) for k, f in lgas.items()}
    keys = list(polys)
    tree = STRtree([polys[k] for k in keys])

    def containing_lga(pt: Point) -> str | None:
        for i in tree.query(pt, predicate="within"):
            return keys[int(i)]
        return None

    pts = [Point(lon, lat) for lat, lon in zip(fac["latitude"], fac["longitude"])]
    fac["lga_key"] = fac["lga"].map(lambda x: norm_key(x, aliases))
    fac["in_lga_polygon"] = [polys[k].contains(p) for k, p in zip(fac["lga_key"], pts)]
    fac["dist_to_lga_m"] = [
        0.0 if inside else polys[k].distance(p) * 111_000  # degrees -> metres, approximate
        for k, p, inside in zip(fac["lga_key"], pts, fac["in_lga_polygon"])
    ]
    fac["polygon_lga"] = [containing_lga(p) for p in pts]
    log["outside_own_lga_polygon"] = int((~fac["in_lga_polygon"]).sum())
    log["outside_state"] = int(fac["polygon_lga"].isna().sum())

    lga_code = {norm_key(f["properties"]["lganame"]): f["properties"]["lgacode"] for f in lga_fc["features"]}
    lga_name = {norm_key(f["properties"]["lganame"]): f["properties"]["lganame"] for f in lga_fc["features"]}

    dim = pd.DataFrame({
        "facility_id": fac["unique_id"],
        "name": fac["facility_name"],
        "state": state,
        "state_code": code,
        "lga_id": fac["lga_key"].map(lga_code).astype(str),
        "lga": fac["lga_key"].map(lga_name),   # boundary-layer spelling is canonical
        "ward": fac["ward"],
        "latitude": fac["latitude"].round(6),
        "longitude": fac["longitude"].round(6),
        "facility_type": fac["facility_type"],
        "ownership_type": fac["facility_ownership_type"],
        "functional_status": fac["functional"],
        "nhfr_code": fac["nhfr_facility_code"].replace("", None),
        "in_lga_polygon": fac["in_lga_polygon"],
        "in_state": fac["polygon_lga"].notna(),
        "dist_to_lga_m": fac["dist_to_lga_m"].round(0),
        # ok / near_boundary (mapped) / location_unverified (kept in queues, not mapped).
        "coord_status": [coord_status(inside, d, near_km)
                         for inside, d in zip(fac["in_lga_polygon"], fac["dist_to_lga_m"])],
        # Linkage keys to DHIS2 / NHLMIS. In a pilot these come from the state's
        # org unit list; here they are deterministic synthetic mirrors.
        "dhis2_orgunit_uid": fac["unique_id"].map(lambda u: synthetic_uid("ou:" + u)),
        "lmis_facility_code": _lmis_codes(fac["unique_id"], st["grid3_code"]),
    }).sort_values(["lga", "name"]).reset_index(drop=True)

    assert dim["dhis2_orgunit_uid"].is_unique and dim["lmis_facility_code"].is_unique

    dim.to_parquet(paths.staging / "dim_facility.parquet", index=False)
    lga_out = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": f["geometry"], "properties": {
            "lga_id": str(f["properties"]["lgacode"]), "lga": f["properties"]["lganame"],
            "state": state, "state_code": code}}
        for f in lga_fc["features"]]}
    (paths.staging / "dim_lga.geojson").write_text(json.dumps(lga_out), encoding="utf-8")

    log["facilities_loaded"] = len(dim)
    log["lgas"] = int(dim["lga"].nunique())
    log["lga_polygons"] = len(lga_fc["features"])
    log.update({f"coord_{k}": int(v) for k, v in dim["coord_status"].value_counts().items()})
    (paths.logs / "facility_master.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"Facility master {state}:", json.dumps(log))
    return dim
