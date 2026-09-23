"""Generated firmware must compile/parse, and must compute the same thing as the engines.

* MicroPython output is executed under CPython with fake ``machine``/``time``/``select``.
* Arduino output is compiled with the host g++ against tiny stub headers and, for the
  arm, run through a harness that compares its IK with the backend's.
"""

import ast
import shutil
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from app.engines.codegen.generator import CodegenError, generate
from app.engines.mechanical import arm
from app.schemas.design import ArmDesign, RoverDesign

STUBS = Path(__file__).parent / "arduino_stubs"
GXX = shutil.which("g++")
BOARDS = ["arduino-uno", "arduino-nano", "esp32-devkit", "rpi-pico"]
MICROPYTHON_BOARDS = ["esp32-devkit", "rpi-pico"]


# --------------------------------------------------------------------------- fake MicroPython


class FakeClock:
    def __init__(self):
        self.ms = 0.0


def fake_micropython(monkeypatch):
    clock = FakeClock()
    pwm_log: dict[int, int] = {}

    time_mod = types.ModuleType("time")
    time_mod.ticks_ms = lambda: int(clock.ms)
    time_mod.ticks_diff = lambda a, b: a - b
    time_mod.sleep_ms = lambda ms: setattr(clock, "ms", clock.ms + ms)
    time_mod.sleep_us = lambda us: setattr(clock, "ms", clock.ms + us / 1000)

    machine = types.ModuleType("machine")

    class Pin:
        OUT, IN = 1, 0

        def __init__(self, n, mode=None, value=None):
            self.n, self._v = n, value or 0

        def value(self, v=None):
            if v is None:
                return self._v
            self._v = v

    class PWM:
        def __init__(self, pin, freq=None):
            self.pin = pin

        def freq(self, f):
            self.f = f

        def duty_u16(self, d):
            assert 0 <= d <= 65535
            pwm_log[self.pin.n] = d

        def duty_ns(self, ns):
            assert 400_000 <= ns <= 2_600_000, "servo pulse out of range"
            pwm_log[self.pin.n] = ns

    machine.Pin, machine.PWM = Pin, PWM
    machine.time_pulse_us = lambda pin, level, timeout: -1  # nothing in front of the sensor

    select_mod = types.ModuleType("select")
    select_mod.POLLIN = 1

    class Poll:
        def register(self, *_):
            pass

        def poll(self, _):
            return []

    select_mod.poll = Poll
    for name, mod in (("time", time_mod), ("machine", machine), ("select", select_mod)):
        monkeypatch.setitem(sys.modules, name, mod)
    return clock, pwm_log


def run_micropython(code, monkeypatch):
    clock, pwm_log = fake_micropython(monkeypatch)
    namespace = {"__name__": "robocraft_generated"}
    exec(compile(code, "main.py", "exec"), namespace)  # noqa: S102 - our own generated code
    return namespace, clock, pwm_log


# --------------------------------------------------------------------------- C++ helpers


def compile_cpp(tmp_path, sketch: str, harness: str | None = None) -> Path | None:
    (tmp_path / "sketch.ino").write_text(sketch)
    base = ["g++", "-std=gnu++17", "-Wall", "-Wextra", "-Werror", f"-I{STUBS}",
            "-include", "Arduino.h"]
    if harness is None:
        subprocess.run([*base, "-fsyntax-only", "-x", "c++", str(tmp_path / "sketch.ino")],
                       check=True, capture_output=True, text=True)
        return None
    (tmp_path / "harness.cpp").write_text(f'#include "sketch.ino"\n{harness}')
    exe = tmp_path / "harness"
    proc = subprocess.run([*base, str(tmp_path / "harness.cpp"), str(STUBS / "stub_runtime.cpp"),
                           "-o", str(exe)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return exe


def ik_targets(design, n=60, seed=3):
    rng = np.random.default_rng(seed)
    targets = [arm.forward(design, [rng.uniform(lo, hi) for lo, hi in arm.JOINT_LIMITS_DEG])["ee"]
               for _ in range(n)]
    targets += [[0.5, 0.0, 0.1], [0.0, 0.0, design.base_height], [-0.1, 0.05, 0.15]]
    return targets


# --------------------------------------------------------------------------- tests


def test_micropython_rejected_on_avr(catalog):
    with pytest.raises(CodegenError):
        generate(ArmDesign(board="arduino-uno"), catalog, "micropython")


@pytest.mark.parametrize("board", MICROPYTHON_BOARDS)
def test_micropython_arm_ik_matches_backend(catalog, board, monkeypatch):
    design = ArmDesign(board=board, upper_arm_length=0.15, forearm_length=0.11)
    out = generate(design, catalog, "micropython")
    assert out["filename"] == "main.py"
    ast.parse(out["code"])
    ns, _, pwm = run_micropython(out["code"], monkeypatch)
    for target in ik_targets(design):
        q, exact = ns["solve_ik"](*target)
        ref = arm.inverse(design, target)
        assert exact == ref.exact
        assert q == pytest.approx(list(ref.q_deg), abs=1e-6)
    ns["run_demo"]()  # executes the whole pick-and-place routine on the fake clock
    assert ns["current"] == pytest.approx(list(arm.HOME_DEG))
    assert len(pwm) == 4


@pytest.mark.parametrize("board", MICROPYTHON_BOARDS)
@pytest.mark.parametrize("driver", ["l298n", "tb6612fng", "mdd10a"])
@pytest.mark.parametrize("sensor", [True, False])
def test_micropython_rover_runs_program(catalog, board, driver, sensor, monkeypatch):
    design = RoverDesign(board=board, motor_driver=driver, obstacle_sensor=sensor)
    out = generate(design, catalog, "micropython", preset="figure8")
    ast.parse(out["code"])
    ns, clock, pwm = run_micropython(out["code"], monkeypatch)
    ns["run_program"]()
    total_ms = sum(ms for _, _, ms in ns["PROGRAM"])
    assert clock.ms >= total_ms
    assert ns["state"]["target"] == [0, 0]
    assert pwm and all(0 <= d <= 65535 for d in pwm.values())


@pytest.mark.skipif(GXX is None, reason="g++ not installed")
@pytest.mark.parametrize("board", BOARDS)
def test_arduino_arm_compiles_and_ik_matches_backend(catalog, board, tmp_path):
    design = ArmDesign(board=board, upper_arm_length=0.13, forearm_length=0.12)
    out = generate(design, catalog, "arduino")
    assert out["filename"].endswith(".ino")
    harness = r"""
int main() {
  setup();
  runDemo();
  float x, y, z;
  while (scanf("%f %f %f", &x, &y, &z) == 3) {
    float q[3];
    bool ok = solveIK(x, y, z, q);
    printf("%d %.5f %.5f %.5f\n", ok ? 1 : 0, q[0], q[1], q[2]);
  }
  return 0;
}
"""
    exe = compile_cpp(tmp_path, out["code"], harness)
    targets = ik_targets(design)
    stdin = "\n".join(" ".join(f"{v:.6f}" for v in t) for t in targets)
    proc = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, check=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln[:2] in ("0 ", "1 ")]
    assert len(lines) == len(targets)
    for target, line in zip(targets, lines, strict=True):
        ok, *q = line.split()
        ref = arm.inverse(design, target)
        assert bool(int(ok)) == ref.exact
        assert [float(v) for v in q] == pytest.approx(list(ref.q_deg), abs=0.05)


@pytest.mark.skipif(GXX is None, reason="g++ not installed")
@pytest.mark.parametrize("board", BOARDS)
@pytest.mark.parametrize("driver", ["l298n", "tb6612fng", "mdd10a"])
@pytest.mark.parametrize("sensor", [True, False])
def test_arduino_rover_compiles_and_runs_program(catalog, board, driver, sensor, tmp_path):
    design = RoverDesign(board=board, motor_driver=driver, obstacle_sensor=sensor)
    out = generate(design, catalog, "arduino", preset="square")
    harness = r"""
int main() {
  setup();
  runProgram();
  printf("elapsed_ms %lu\n", millis());
  return 0;
}
"""
    exe = compile_cpp(tmp_path, out["code"], harness)
    proc = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
    assert "Demo finished." in proc.stdout
    elapsed = int(proc.stdout.split("elapsed_ms")[-1])
    program = [line for line in out["code"].splitlines() if line.strip().startswith("{ ")
               and "//" in line]
    assert elapsed >= sum(int(p.split(",")[2].split("}")[0]) for p in program)


HOSTILE_NAMES = ['Arm */ int x = ; /*', 'Rov """ import os', 'a""";import machine;"""',
                 "back\\slash\nnew line", "*/"]


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_design_name_cannot_break_out_of_comments(catalog, name, tmp_path, monkeypatch):
    for design in (ArmDesign(name=name, board="esp32-devkit"),
                   RoverDesign(name=name, board="esp32-devkit")):
        py = generate(design, catalog, "micropython")["code"]
        # The name must stay inside the module docstring, not end it early.
        assert "Generated by RoboCraft" in ast.get_docstring(ast.parse(py))
        cpp = generate(design, catalog, "arduino")["code"]
        assert cpp.index("*/") > cpp.index("SERIAL COMMANDS")  # header comment closes once
        if GXX:
            compile_cpp(tmp_path, cpp)


def test_generated_code_carries_engine_decisions(catalog):
    design = RoverDesign(board="esp32-devkit")
    out = generate(design, catalog, "arduino")
    assert "GPIO34" in out["code"]  # echo pin from the electrical engine
    assert "PROGRAM[]" in out["code"]
    arm_out = generate(ArmDesign(board="esp32-devkit"), catalog, "arduino")
    assert "#include <ESP32Servo.h>" in arm_out["code"]
    assert any("ESP32Servo" in lib for lib in arm_out["libraries"])
