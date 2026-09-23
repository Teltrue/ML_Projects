import pytest

from app.engines.electrical.selection import (
    KGCM_TO_NM,
    select_drivetrain,
    select_servo,
    servo_torque_kgcm,
)
from app.pipeline import DesignError, analyze
from app.schemas.design import ArmDesign, RoverDesign


def checks_by_id(result):
    return {c["id"]: c for c in result["mechanical"]["checks"] + result["electrical"]["checks"]}


def assert_netlist_consistent(result):
    elec = result["electrical"]
    refs = {p["ref"]: p for p in elec["parts"]}
    for wire in elec["wires"]:
        assert wire["a"] in refs and wire["b"] in refs
        assert wire["a_pin"] in refs[wire["a"]]["pins"]
        assert wire["b_pin"] in refs[wire["b"]]["pins"]
    assert len(set(elec["pin_map"].values())) == len(elec["pin_map"]), "MCU pin used twice"
    mcu = elec["parts"][0]
    assert any(w["net"] == "GND" and mcu["ref"] in (w["a"], w["b"]) for w in elec["wires"])
    assert sum(item["qty"] for item in elec["bom"]) == len(elec["parts"])


def test_servo_torque_interpolation(catalog):
    mg996r = catalog.get("mg996r")
    assert servo_torque_kgcm(mg996r, 4.8) == pytest.approx(9.4)
    assert servo_torque_kgcm(mg996r, 5.4) == pytest.approx(10.2)
    assert servo_torque_kgcm(mg996r, 7.0) == pytest.approx(11.0)  # never extrapolate upward
    assert servo_torque_kgcm(mg996r, 2.4) == pytest.approx(4.7)


def test_servo_selection_keeps_ten_percent_headroom(catalog):
    sel = select_servo("elbow", "Elbow", 1.95 * KGCM_TO_NM, 6.0, catalog)
    assert sel.status == "ok"
    assert sel.utilisation <= 0.9
    assert sel.component.id != "sg90"  # 1.95 of 2.0 kg·cm would be too tight


def test_servo_selection_reports_impossible_requirements(catalog):
    sel = select_servo("shoulder", "Shoulder", 500 * KGCM_TO_NM, 6.0, catalog)
    assert sel.status == "insufficient"
    assert sel.component.id == "rds5160"


def test_default_arm_is_feasible_and_isolates_servo_power(catalog):
    result = analyze(ArmDesign(), catalog)
    assert result["summary"]["status"] == "ok"
    checks = checks_by_id(result)
    assert checks["servo-power-isolation"]["auto_fixed"]
    assert checks["common-ground"]["severity"] == "pass"
    assert result["electrical"]["power_source_id"] == "psu-6v-5a"
    assert {a["role"] for a in result["electrical"]["actuators"]} == {
        "base", "shoulder", "elbow", "gripper"}
    assert_netlist_consistent(result)


def test_servo_masses_feed_back_into_the_shoulder_load(catalog):
    result = analyze(ArmDesign(), catalog)
    masses = result["mechanical"]["actuator_masses_kg"]
    elbow = next(a for a in result["electrical"]["actuators"] if a["role"] == "elbow")
    assert masses["elbow"] == pytest.approx(catalog.get(elbow["component_id"]).mass_kg)


def test_lipo_arm_gets_regulator_fuse_and_switch(catalog):
    result = analyze(ArmDesign(power_source="batt-2s-lipo"), catalog)
    categories = {b["category"] for b in result["electrical"]["bom"]}
    assert {"regulator", "safety"} <= categories
    checks = checks_by_id(result)
    assert checks["servo-regulator-added"]["auto_fixed"]
    assert checks["battery-protection"]["auto_fixed"]
    rail = result["electrical"]["rails"][0]
    assert rail["voltage"] == 6.0
    assert_netlist_consistent(result)


def test_overloaded_arm_reports_errors(catalog):
    result = analyze(ArmDesign(payload_mass=3.0, upper_arm_length=0.4, forearm_length=0.4),
                     catalog)
    assert result["summary"]["status"] == "error"
    assert checks_by_id(result)["payload"]["severity"] == "error"


def test_default_rover_uses_l298n_with_onboard_regulator(catalog):
    result = analyze(RoverDesign(), catalog)
    assert result["summary"]["status"] == "ok"
    elec = result["electrical"]
    assert elec["driver_id"] == "l298n"
    checks = checks_by_id(result)
    assert checks["logic-rail"]["severity"] == "pass"
    assert checks["logic-level-echo"]["severity"] == "pass"  # 5 V Uno reads 5 V ECHO directly
    assert set(elec["pin_map"]) == {"ena", "enb", "in1", "in2", "in3", "in4", "trig", "echo"}
    # PWM-capable pins for the enables
    uno_pwm = {3, 5, 6, 9, 10, 11}
    assert elec["pin_map"]["ena"] in uno_pwm and elec["pin_map"]["enb"] in uno_pwm
    assert_netlist_consistent(result)


def test_3v3_board_gets_level_shifter_on_echo(catalog):
    result = analyze(RoverDesign(board="esp32-devkit"), catalog)
    parts = {p["component_id"] for p in result["electrical"]["parts"]}
    assert "level-shifter-4ch" in parts
    check = checks_by_id(result)["logic-level-echo"]
    assert check["auto_fixed"] and "ESP32" in check["title"]
    # The sensor's 5 V echo must never be wired straight to the ESP32.
    mcu = result["electrical"]["parts"][0]["ref"]
    sensor = next(p["ref"] for p in result["electrical"]["parts"]
                  if p["component_id"] == "hc-sr04")
    for w in result["electrical"]["wires"]:
        assert not ({w["a"], w["b"]} == {mcu, sensor} and "ECHO" in (w["a_pin"], w["b_pin"]))
    assert_netlist_consistent(result)


def test_3s_lipo_bypasses_l298n_regulator(catalog):
    result = analyze(RoverDesign(power_source="batt-3s-lipo", motor_driver="l298n"), catalog)
    check = checks_by_id(result)["logic-rail"]
    assert check["auto_fixed"] and "12.6" in check["detail"]
    assert any(p["category"] == "regulator" for p in result["electrical"]["parts"])


def test_4wd_doubles_channel_current(catalog):
    design = RoverDesign(drive_motors=4)
    best, _ = select_drivetrain(design, catalog)
    assert best.motors_per_channel == 2
    result = analyze(design, catalog)
    motors = [p for p in result["electrical"]["parts"] if p["category"] == "dc_motor"]
    assert len(motors) == 4
    assert_netlist_consistent(result)


def test_tb6612_logic_supply_follows_board(catalog):
    result = analyze(RoverDesign(board="rpi-pico", motor_driver="tb6612fng"), catalog)
    wires = result["electrical"]["wires"]
    vcc = next(w for w in wires if w["b_pin"] == "VCC")
    assert vcc["a_pin"] == "3V3(OUT)"
    assert "stby" in result["electrical"]["pin_map"]


def test_impossible_rover_still_returns_explained_errors(catalog):
    design = RoverDesign(chassis_mass=10, payload_mass=10, max_incline=30, max_accel=3)
    result = analyze(design, catalog)
    assert result["summary"]["status"] == "error"
    assert any(c["id"].startswith("drivetrain-") for c in result["electrical"]["checks"])


@pytest.mark.parametrize("board", ["arduino-uno", "arduino-nano", "esp32-devkit", "rpi-pico"])
@pytest.mark.parametrize("driver", ["l298n", "tb6612fng", "mdd10a"])
def test_every_board_driver_combination_wires_up(catalog, board, driver):
    result = analyze(RoverDesign(board=board, motor_driver=driver), catalog)
    assert_netlist_consistent(result)


def test_unknown_board_is_a_design_error(catalog):
    with pytest.raises(DesignError):
        analyze(ArmDesign(board="nope"), catalog)
    with pytest.raises(DesignError):
        analyze(ArmDesign(board="mg996r"), catalog)
    with pytest.raises(DesignError):
        analyze(RoverDesign(power_source="psu-6v-5a"), catalog)
