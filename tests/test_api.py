import time

import pytest
from fastapi.testclient import TestClient

import circwaste.api.main as main
import circwaste.scenario.whatif as whatif


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    whatif.CACHE = tmp_path_factory.mktemp("whatif_cache")      # never touch the committed precomputed grid
    main.WORKERS = 1
    return TestClient(main.app)


def test_health_and_base(client):
    assert client.get("/health").json()["synthetic"] is True
    b = client.get("/base").json()
    assert b["synthetic"] is True and "OpenStreetMap" in b["attribution"]
    assert len(b["points"]) == 120 and b["depot"]["lat"] and {f["kind"] for f in b["facilities"]} >= {"dwcc", "wet_plant", "landfill"}
    assert b["wards"]["features"]


def test_policies(client):
    p = client.get("/policies").json()
    assert [x["name"] for x in p["policies"]] == ["threshold", "overflow_only", "recovery_aware", "value_only"]


def test_scenario_job_day_and_cache(client):
    body = {"levers": {"policy": "overflow_only"}, "seeds": [100], "eval_days": 2}
    j = client.post("/scenario", json=body).json()
    assert j["status"] in ("queued", "running", "done")
    for _ in range(300):
        j = client.get(f"/scenario/{j['id']}").json()
        if j["status"] in ("done", "failed"):
            break
        time.sleep(1)
    assert j["status"] == "done", j.get("error")
    assert j["result"]["synthetic"] is True and "detail" not in j["result"]
    assert j["result"]["summary"]["mean"]["overflow_events"] >= 0
    d = client.get(f"/day/{j['id']}/1").json()
    assert d["synthetic"] is True and d["routes"]["features"] and d["routes"]["features"][0]["geometry"]["type"] == "LineString"
    assert len(d["bins"]) == 120 and all("overflow_risk" in x for x in d["bins"])
    assert client.get(f"/day/{j['id']}/9").status_code == 404
    again = client.post("/scenario", json=body).json()          # identical request -> same id, already done
    assert again["id"] == j["id"] and again["status"] == "done"
    assert client.get("/scenario/nope").status_code == 404


def test_validation_and_experiments(client):
    assert client.post("/scenario", json={"levers": {"policy": "magic"}}).status_code == 422
    assert client.post("/scenario", json={"levers": {"segregation_rate": 1.5}}).status_code == 422
    e = client.get("/experiments").json()
    assert e["synthetic"] is True and "main" in e
