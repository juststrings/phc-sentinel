"""Synthetic people directory: who holds each role at national, state, LGA and facility level.

Every person is SYNTHETIC (synthetic=True). Names are random first-name x surname draws from generic
name pools (config/name_pools.yaml), re-drawn if they hit a blocked well-known full name. Contacts are
non-real by construction: phones are `SIM-{STATE}-{6 digits}` (not dialable) and emails end in the
reserved `.invalid` TLD (cannot deliver). Generation is seeded per state, so a state's directory never
changes when other states are added.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..config import ACTIONS_DIR, StatePaths, actions_cfg, name_pools, settings, states

LEVEL_ORDER = {"national": 0, "state": 1, "lga": 2, "facility": 3}
ZONES_NORTH = {"North West", "North East", "North Central"}


def roles_table() -> pd.DataFrame:
    rows = []
    for code, r in actions_cfg()["roles"].items():
        rows.append({"role_code": code, "level": r["level"], "title": r["title"], "per_unit": r.get("per", 1),
                     "responsibilities": r["responsibilities"], "owns_playbooks": ",".join(r.get("owns", []))})
    df = pd.DataFrame(rows)
    df["level_order"] = df["level"].map(LEVEL_ORDER)
    return df.sort_values(["level_order", "role_code"]).reset_index(drop=True)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


class _Namer:
    """Draws names for one state with its own generator."""

    def __init__(self, rng: np.random.Generator, zone: str):
        self.rng, self.zone = rng, zone
        cfg = actions_cfg()["directory"]
        np_ = name_pools()
        self.pools = np_["pools"]
        self.zones = list(self.pools)
        self.hon = np_["honorifics"]
        self.blocked = {b.lower() for b in np_.get("blocked_full_names", [])}
        self.female_share, self.cross, self.hon_share = cfg["female_share"], cfg["cross_zone_share"], cfg["honorific_share"]

    def draw(self, senior: bool) -> tuple[str, str, str, str]:
        r = self.rng
        gender = "female" if r.random() < self.female_share else "male"
        zone = self.zone if r.random() >= self.cross else self.zones[int(r.integers(len(self.zones)))]
        pool = self.pools[zone]
        while True:
            first = pool[gender][int(r.integers(len(pool[gender])))]
            last = pool["surname"][int(r.integers(len(pool["surname"])))]
            if f"{first} {last}".lower() not in self.blocked and first != last:
                break
        title = ""
        if r.random() < self.hon_share * (2.0 if senior else 1.0):
            opts = list(self.hon["any"]) + [h for h in self.hon[gender]
                                             if zone in ZONES_NORTH or h not in self.hon["north_only"]]
            title = opts[int(r.integers(len(opts)))]
        return first, last, gender, title


def _channel(rng: np.random.Generator, facility: bool) -> str:
    d = actions_cfg()["directory"]["channels" if facility else "officer_channels"]
    keys = list(d)
    p = np.array([d[k] for k in keys], dtype=float)
    return keys[int(rng.choice(len(keys), p=p / p.sum()))]


def _responsiveness(rng: np.random.Generator, lga_mean: float) -> tuple[float, bool]:
    c = actions_cfg()["directory"]["responsiveness"]
    k = c["person_concentration"]
    never = rng.random() < c["never_reply_share"]
    v = float(rng.beta(max(lga_mean * k, 0.5), max((1 - lga_mean) * k, 0.5)))
    return (round(0.0 if never else v, 3), bool(never))


def _people_for_state(st: dict, roles: pd.DataFrame) -> list[dict]:
    seed = settings()["simulator"]["seed"] + actions_cfg()["directory"]["seed_offset"] + st["sim"]["seed_offset"]
    rng = np.random.default_rng(seed)
    namer = _Namer(rng, st["zone"])
    rc = actions_cfg()["directory"]["responsiveness"]
    dim = pd.read_parquet(StatePaths(st["code"]).staging / "dim_facility.parquet")
    lgas = dim[["lga_id", "lga"]].drop_duplicates().sort_values("lga_id")
    lga_mean = {l: float(rng.beta(rc["lga_mean_alpha"], rc["lga_mean_beta"])) for l in lgas["lga_id"]}
    state_mean = float(np.mean(list(lga_mean.values())))
    code, g3 = st["code"], st["grid3_code"]
    used_phone: set[str] = set()
    out: list[dict] = []

    def add(role, level, lga_id=None, lga=None, facility_id=None, facility=None):
        first, last, gender, title = namer.draw(senior=level in ("state",))
        while True:
            phone = f"SIM-{g3}-{int(rng.integers(0, 1_000_000)):06d}"
            if phone not in used_phone:
                used_phone.add(phone)
                break
        resp, never = _responsiveness(rng, lga_mean.get(lga_id, state_mean))
        out.append({
            "person_id": f"P-{g3}-{len(out) + 1:06d}", "first_name": first, "last_name": last, "honorific": title,
            "name": f"{title + ' ' if title else ''}{first} {last}", "gender": gender,
            "role_code": role, "level": level, "state_code": code, "zone": st["zone"],
            "lga_id": lga_id, "lga": lga, "facility_id": facility_id, "facility": facility,
            "phone_display": phone, "email_local": f"{_slug(first)}.{_slug(last)}",
            "preferred_channel": _channel(rng, level == "facility"),
            "responsiveness": resp, "never_replies": never, "active": True, "synthetic": True,
        })

    for r in roles[roles["level"] == "state"].itertuples():
        for _ in range(r.per_unit):
            add(r.role_code, "state")
    lga_roles = roles[roles["level"] == "lga"]
    for l in lgas.itertuples():
        for r in lga_roles.itertuples():
            for _ in range(r.per_unit):
                add(r.role_code, "lga", l.lga_id, l.lga)
    fac_roles = roles[roles["level"] == "facility"]
    for f in dim.itertuples():
        for r in fac_roles.itertuples():
            for _ in range(r.per_unit):
                add(r.role_code, "facility", f.lga_id, f.lga, f.facility_id, f.name)
    return out


def _national(roles: pd.DataFrame) -> list[dict]:
    rng = np.random.default_rng(settings()["simulator"]["seed"] + actions_cfg()["directory"]["seed_offset"] + 999)
    zones = settings()["zones"]
    out = []
    for r in roles[roles["level"] == "national"].itertuples():
        zone = zones[int(rng.integers(len(zones)))]
        first, last, gender, title = _Namer(rng, zone).draw(senior=True)
        out.append({
            "person_id": f"P-NG-{len(out) + 1:06d}", "first_name": first, "last_name": last, "honorific": title,
            "name": f"{title + ' ' if title else ''}{first} {last}", "gender": gender,
            "role_code": r.role_code, "level": "national", "state_code": None, "zone": None,
            "lga_id": None, "lga": None, "facility_id": None, "facility": None,
            "phone_display": f"SIM-NG-{int(rng.integers(0, 1_000_000)):06d}", "email_local": f"{_slug(first)}.{_slug(last)}",
            "preferred_channel": "email", "responsiveness": round(float(rng.beta(6, 2.5)), 3), "never_replies": False,
            "active": True, "synthetic": True,
        })
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    roles = roles_table()
    rows = _national(roles)
    for st in states():
        rows.extend(_people_for_state(st, roles))
    people = pd.DataFrame(rows)
    # Emails: firstname.lastname@{state}.sentinel-demo.invalid, numbered when two people share a name.
    domain = people["state_code"].fillna("national")
    local = people["email_local"]
    n = people.groupby([domain, local]).cumcount()
    people["email"] = local + n.map(lambda k: "" if k == 0 else str(k + 1)) + "@" + domain + ".sentinel-demo.invalid"
    people = people.drop(columns=["email_local"])
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    roles.to_parquet(ACTIONS_DIR / "dim_role.parquet", index=False)
    people.to_parquet(ACTIONS_DIR / "dim_person.parquet", index=False)
    print(f"Directory: {len(people):,} synthetic people "
          f"({people['level'].value_counts().reindex(list(LEVEL_ORDER)).to_dict()})")
    return roles, people


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    p = ACTIONS_DIR / "dim_person.parquet"
    if not p.exists():
        return build()
    return pd.read_parquet(ACTIONS_DIR / "dim_role.parquet"), pd.read_parquet(p)
