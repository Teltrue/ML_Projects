def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_templates_expose_ui_metadata(client):
    templates = {t["id"]: t for t in client.get("/api/templates").json()}
    assert set(templates) == {"arm", "rover"}
    params = {p["key"]: p for p in templates["arm"]["parameters"]}
    assert params["upper_arm_length"]["kind"] == "slider"
    assert params["upper_arm_length"]["scale"] == 1000
    boards = [o["value"] for o in params["board"]["options"]]
    assert "esp32-devkit" in boards
    rover_sources = {p["key"]: p for p in templates["rover"]["parameters"]}["power_source"]
    assert all(o["value"] == "auto" or o["value"].startswith("batt")
               for o in rover_sources["options"])


def test_components_filter(client):
    servos = client.get("/api/components", params={"category": "servo"}).json()
    assert servos and all(c["category"] == "servo" for c in servos)


def test_analyze_both_templates(client):
    for template in ("arm", "rover"):
        res = client.post("/api/analyze", json={"design": {"template": template}})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["template"] == template
        assert body["electrical"]["bom"]


def test_analyze_validation_errors(client):
    res = client.post("/api/analyze", json={"design": {"template": "arm", "payload_mass": -1}})
    assert res.status_code == 422
    res = client.post("/api/analyze", json={"design": {"template": "arm", "board": "nope"}})
    assert res.status_code == 422
    assert "Unknown microcontroller" in res.json()["detail"]


def test_arm_pose_ik_and_fk(client):
    design = {"template": "arm"}
    ik = client.post("/api/arm/pose", json={"design": design, "target": [0.15, 0.05, 0.12]})
    assert ik.status_code == 200
    body = ik.json()
    assert body["exact"]
    fk = client.post("/api/arm/pose", json={"design": design, "mode": "fk",
                                            "joints": body["q_deg"]}).json()
    assert abs(fk["ee"][0] - 0.15) < 1e-6 and abs(fk["ee"][2] - 0.12) < 1e-6
    low = client.post("/api/arm/pose", json={"design": design, "mode": "fk",
                                             "joints": [0, 0, -120]}).json()
    assert any("table" in w for w in low["warnings"])


def test_arm_trajectory_demo_and_custom(client):
    demo = client.post("/api/arm/trajectory", json={"design": {"template": "arm"}}).json()
    assert demo["duration"] > 0 and len(demo["samples"]) > 10
    custom = client.post("/api/arm/trajectory", json={
        "design": {"template": "arm"},
        "waypoints": [{"label": "a", "position": [0.15, 0, 0.1], "gripper": 1}],
    }).json()
    assert custom["waypoints"][0]["label"] == "home"


def test_rover_simulation(client):
    res = client.post("/api/rover/simulate", json={"design": {"template": "rover"},
                                                   "preset": "spin"})
    assert res.status_code == 200
    body = res.json()
    assert body["preset"] == "spin" and body["samples"]


def test_codegen_endpoint(client):
    res = client.post("/api/codegen", json={"design": {"template": "arm"},
                                            "language": "arduino"})
    assert res.status_code == 200
    assert "solveIK" in res.json()["code"]
    res = client.post("/api/codegen", json={"design": {"template": "arm"},
                                            "language": "micropython"})
    assert res.status_code == 422


def test_project_crud(client):
    created = client.post("/api/projects", json={"name": "Desk arm",
                                                 "design": {"template": "arm"}})
    assert created.status_code == 201
    project = created.json()
    assert project["template"] == "arm"
    pid = project["id"]
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    design = project["design"] | {"payload_mass": 0.1}
    updated = client.put(f"/api/projects/{pid}", json={"name": "Renamed", "design": design})
    assert updated.json()["design"]["payload_mass"] == 0.1
    assert client.put(f"/api/projects/{pid}", json={
        "name": "x", "design": {"template": "rover"}}).status_code == 422
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
