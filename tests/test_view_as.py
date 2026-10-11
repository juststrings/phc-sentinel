"""The View-as filter: every request is checked against the viewer's scope, and no row from another state or LGA comes back.
Needs the loaded PostGIS database (skips otherwise)."""
import pytest

from sentinel import viewas

NAT = {"X-View-As": "national"}
BAUCHI = {"X-View-As": "state:bauchi"}
TORO = {"X-View-As": "lga:bauchi:5018"}          # an LGA of Bauchi (the seeded demo LGA)
KANO_LGA = "20021"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from sentinel.api import main
    try:
        with main._engine().connect() as c:
            c.execute(text("SELECT 1 FROM case_file LIMIT 1"))
    except Exception:
        pytest.skip("PostGIS with the action layer loaded is not available")
    return TestClient(main.app)


def get(client, path, headers=None, **params):
    return client.get(path, headers=headers or {}, params=params)


def state_codes_in(obj, found=None):
    """Every value of a `state_code` key anywhere in a JSON response."""
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "state_code" and isinstance(v, str):
                found.add(v)
            else:
                state_codes_in(v, found)
    elif isinstance(obj, list):
        for v in obj:
            state_codes_in(v, found)
    return found


# ---- parsing ----------------------------------------------------------------------------------------------
def test_parse_header_forms():
    assert viewas.parse("national") == viewas.NATIONAL
    assert viewas.parse("state:kano") == viewas.Scope("state", "kano")
    assert viewas.parse("lga:kano:20021") == viewas.Scope("lga", "kano", "20021")
    assert viewas.parse(None) is None
    for bad in ("state:atlantis", "lga:kano", "everything", "state:"):
        with pytest.raises(Exception):
            viewas.parse(bad)


def test_no_scope_means_no_rows_but_names_stay_open(client):
    assert get(client, "/state/bauchi/summary").status_code == 401
    assert get(client, "/national/summary").status_code == 401
    assert get(client, "/health").status_code == 200
    assert get(client, "/meta/states").status_code == 200
    assert client.get("/state/bauchi/summary", headers={"X-View-As": "state:atlantis"}).status_code == 400


# ---- who can open what -------------------------------------------------------------------------------------
def test_national_sees_everything(client):
    for p in ("/national/summary", "/state/kano/summary", "/state/bauchi/lga/5018/queue", "/state/kano/facilities"):
        assert get(client, p, NAT).status_code == 200, p


def test_state_board_is_limited_to_its_state(client):
    assert get(client, "/state/bauchi/summary", BAUCHI).status_code == 200
    assert get(client, "/state/bauchi/lga/5018/queue", BAUCHI).status_code == 200
    for p in ("/state/kano/summary", "/state/kano/facilities", f"/state/kano/lga/{KANO_LGA}/queue", "/national/summary",
              "/national/states", "/state/summary", "/state/top", "/geo/lgas", f"/lga/{KANO_LGA}/queue"):
        assert get(client, p, BAUCHI).status_code == 403, p


def test_lga_view_is_limited_to_its_lga(client):
    assert get(client, "/state/bauchi/lga/5018/queue", TORO).status_code == 200
    other = next(l["lga_id"] for l in get(client, "/state/bauchi/summary", NAT).json()["lgas"] if l["lga_id"] != "5018")
    for p in (f"/state/bauchi/lga/{other}/queue", "/state/bauchi/summary", "/state/bauchi/top", "/state/bauchi/geo/lgas",
              "/state/bauchi/insights", "/state/bauchi/actions/summary", "/state/kano/summary", "/national/summary"):
        assert get(client, p, TORO).status_code == 403, p


def test_facility_pages_follow_the_lga(client):
    q = get(client, "/state/bauchi/lga/5018/queue", NAT).json()
    inside = (q["action"] + q["verification"] + q["monitor"])[0]["facility_id"]
    other_lga = next(l["lga_id"] for l in get(client, "/state/bauchi/summary", NAT).json()["lgas"] if l["lga_id"] != "5018")
    q2 = get(client, f"/state/bauchi/lga/{other_lga}/queue", NAT).json()
    outside = (q2["action"] + q2["verification"] + q2["monitor"])[0]["facility_id"]
    assert get(client, f"/state/bauchi/facility/{inside}", TORO).status_code == 200
    assert get(client, f"/state/bauchi/facility/{outside}", TORO).status_code == 403
    assert get(client, f"/state/bauchi/facility/{outside}", BAUCHI).status_code == 200


def test_only_national_resets_the_simulation(client):
    assert client.post("/sim/reset", headers=BAUCHI).status_code == 403
    assert client.post("/sim/reset", headers=TORO).status_code == 403


# ---- rows are filtered, not just routes --------------------------------------------------------------------
def test_directory_and_search_return_only_the_viewers_rows(client):
    d = get(client, "/facilities", BAUCHI, page_size=100).json()
    assert d["facilities"] and {f["state_code"] for f in d["facilities"]} == {"bauchi"}
    assert get(client, "/facilities", BAUCHI, state="kano").status_code == 403
    d = get(client, "/facilities", TORO, page_size=100).json()
    assert d["facilities"] and {f["lga_id"] for f in d["facilities"]} == {"5018"}
    assert get(client, "/facilities", TORO, state="bauchi", lga_id="5001").status_code == 403
    s = get(client, "/search", BAUCHI, q="health").json()
    assert s["facilities"] and {f["state_code"] for f in s["facilities"]} == {"bauchi"}
    assert get(client, "/search", NAT, q="health").json()["total"] > s["total"]


def test_lists_of_cases_messages_responses_and_people_are_clamped(client):
    nat_bauchi = get(client, "/state/bauchi/cases", NAT, limit=1000).json()
    lga_cases = get(client, "/state/bauchi/cases", TORO, limit=1000).json()
    assert 0 < lga_cases["total"] < nat_bauchi["total"]
    assert {c["lga_id"] for c in lga_cases["cases"]} == {"5018"}
    assert get(client, "/state/kano/cases", BAUCHI).status_code == 403
    assert get(client, "/messages", BAUCHI, state="kano").status_code == 403
    assert get(client, "/messages", BAUCHI).json()["total"] == get(client, "/messages", NAT, state="bauchi").json()["total"]
    assert get(client, "/messages", TORO).json()["total"] == get(client, "/messages", NAT, state="bauchi", lga_id="5018").json()["total"]
    assert get(client, "/responses", BAUCHI, state="kano").status_code == 403
    people = get(client, "/state/bauchi/people", TORO, limit=2000).json()["people"]
    assert people and {p["lga_id"] for p in people} == {"5018"}


def test_cases_and_people_by_id_respect_the_view(client):
    kano = get(client, "/state/kano/cases", NAT, limit=5).json()["cases"][0]
    assert get(client, f"/cases/{kano['case_id']}", BAUCHI).status_code == 403
    assert get(client, f"/cases/{kano['case_id']}", NAT).status_code == 200
    bauchi_cases = get(client, "/state/bauchi/cases", NAT, limit=1000).json()["cases"]
    elsewhere = next(c for c in bauchi_cases if c["lga_id"] != "5018")
    assert get(client, f"/cases/{elsewhere['case_id']}", BAUCHI).status_code == 200
    assert get(client, f"/cases/{elsewhere['case_id']}", TORO).status_code == 403
    nat_person = get(client, "/meta/signin", NAT, role="national").json()["person"]["person_id"]
    assert get(client, f"/people/{nat_person}", BAUCHI).status_code == 403
    assert get(client, f"/people/{nat_person}", NAT).status_code == 200


def test_you_can_only_act_as_someone_inside_your_view(client):
    case = get(client, "/state/bauchi/cases", NAT, limit=1000).json()["cases"][0]
    kano_dir = get(client, "/meta/signin", NAT, role="state", state="kano").json()["person"]["person_id"]
    nat_dir = get(client, "/meta/signin", NAT, role="national").json()["person"]["person_id"]
    for who in (kano_dir, nat_dir):
        r = client.post(f"/cases/{case['case_id']}/note", headers=BAUCHI, json={"actor_person_id": who, "note": "x"})
        assert r.status_code == 403, who
    personas = get(client, "/meta/personas", BAUCHI).json()["personas"]
    assert personas and all(p["level"] != "national" and p["state_code"] == "bauchi" for p in personas)
    assert get(client, "/meta/personas", BAUCHI, state="kano").status_code == 403


def test_no_other_state_appears_anywhere_in_a_state_viewers_responses(client):
    paths = ["/state/bauchi/summary", "/state/bauchi/top", "/state/bauchi/insights", "/state/bauchi/cases", "/state/bauchi/people",
             "/state/bauchi/actions/summary", "/state/bauchi/geo/facilities", "/messages", "/responses", "/me/cases?persona_id=" ]
    seen = set()
    for p in paths:
        if p.endswith("persona_id="):
            continue
        r = get(client, p, BAUCHI)
        assert r.status_code == 200, p
        seen |= state_codes_in(r.json())
    assert seen <= {"bauchi"}, seen
