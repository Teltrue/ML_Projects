# RoboCraft: the accessible robotics builder (MVP)

RoboCraft is a web app that walks beginners from an idea to a working robot. You shape the
robot in 3D. RoboCraft then does the maths and physics, picks the parts, wires a circuit
that won't damage the board, and writes the firmware.

This folder holds the **Phase 1 MVP** from the architecture document: two pre-rigged
templates (a **3-axis arm** and a **differential-drive rover**) running through all four
engines.

![Arm studio](docs/arm-studio.png)

| Rover driving a simulated figure-8 | Auto-generated wiring (ESP32 + level shifter added for safety) |
| --- | --- |
| ![Rover simulation](docs/rover-simulation.png) | ![Wiring diagram](docs/wiring-diagram.png) |

## What the MVP does

| Engine | Arm template | Rover template |
| --- | --- | --- |
| **Spatial** (Next.js + React Three Fiber) | Live 3D arm, sliders for every link, draggable IK target, reach envelope, centre-of-mass marker, pick-and-place playback with a carried payload | Live 3D rover (2WD + caster or 4WD), sensor stopping zone, playback of square / figure-8 / spin programs with spinning wheels |
| **Mechanical** (FastAPI + NumPy) | Standard DH model, FK, closed-form IK (elbow-up, reach-over-the-top, unreachable targets projected onto the workspace), worst-case gravity + inertia torque over a 5° sweep of the whole workspace, max payload, tip-over check with ballast suggestion, speed/acceleration-limited quintic trajectories | Drive-force budget (rolling resistance, slope, acceleration), wheel RPM, torque and power per motor, traction limit, differential-drive kinematics, exact rest-to-rest path simulation with acceleration ramps |
| **Electrical** (rule engine + PostgreSQL component library) | Servo selection with ≥10% headroom, servo masses fed back into the torque sizing until stable, dedicated servo rail, auto-added buck converter / fuse / switch / bulk capacitor, current and logic-level checks | Joint search over motor × driver × battery, L298N / TB6612FNG / MDD10A wiring, 5 V logic rail (L298N regulator or auto-added buck when a 3S pack exceeds 12 V), auto-added logic level converter for 3.3 V boards, noise capacitors, fuse sizing, runtime estimate |
| **Code generation** (Jinja2 templates) | Arduino C++ (Uno, Nano, ESP32, Pico) and MicroPython (ESP32, Pico): the same IK in firmware, serial commands, calibration constants, the same pick-and-place demo | Arduino C++ and MicroPython: driver-specific motor code, coordinated soft-start ramps, obstacle stop, the same demo programs as the simulator |

Every rule result is shown to the user as a check (pass, info, warning or error). Each
check says why it matters and what to do, and the parts RoboCraft added for safety are
labelled as auto-fixes. Designs can be saved as projects, exported as JSON, and the bill of
materials can be downloaded as CSV.

## Quick start

### Option A: Docker (PostgreSQL + API + web app)

```bash
cd robocraft
docker compose up --build
# open http://localhost:3000   (API docs: http://localhost:8000/docs)
```

### Option B: run locally (SQLite, no database server needed)

```bash
# 1. API (Python 3.11+)
cd robocraft/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs

# 2. Web app (Node 20+), in a second terminal
cd robocraft/frontend
npm install
npm run dev                              # http://localhost:3000
```

The web app proxies `/api/*` to the backend (`BACKEND_URL`, default
`http://127.0.0.1:8000`), so the browser never needs CORS. Set `DATABASE_URL` (for example
`postgresql+psycopg://user:pass@host/db`) to use PostgreSQL instead of the default
`sqlite:///./robocraft.db`.

## Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser: Next.js 16 + React Three Fiber + Tailwind"]
    UI[Parameter panel<br/>generated from /api/templates]
    V[3D viewport<br/>IK gizmo, playback]
    I[Insights: checks, mechanics,<br/>electronics, code]
  end
  UI -- "/api/* (Next rewrite)" --> API
  V --> API
  I --> API
  subgraph API["FastAPI"]
    P[pipeline.py] --> M[Mechanical engine<br/>DH / IK / torque / rover physics]
    P --> E[Electrical engine<br/>selection + rule-checked netlist]
    C[Codegen engine<br/>Jinja2 firmware] --> P
  end
  E --> DB[(PostgreSQL / SQLite<br/>components, projects)]
```

A design flows through `pipeline.py`:

1. **Mechanical** sizes torques (arm) or drive forces (rover) for the geometry and payload.
2. **Electrical** picks parts that meet those requirements. The masses of the chosen parts
   go back into step 1, because a heavier elbow servo loads the shoulder, until the
   selection stops changing. It then builds the netlist and runs the safety rules.
3. **Codegen** renders firmware from the design, the pin map chosen by the Electrical
   Engine, and the same motion maths as the simulator.

```
robocraft/
├── backend/
│   ├── app/
│   │   ├── engines/
│   │   │   ├── mechanical/   kinematics.py (batched DH, Jacobians, M(q)), arm.py, rover.py
│   │   │   ├── electrical/   selection.py, netlist.py, arm_circuit.py, rover_circuit.py
│   │   │   └── codegen/      generator.py + templates/*.j2
│   │   ├── data/components.json   component library (seeded/upserted into the DB)
│   │   ├── schemas/          design.py (parameters + UI metadata), api.py
│   │   ├── routers/          catalog.py, engines.py, projects.py
│   │   ├── pipeline.py       engine orchestration
│   │   └── main.py           app factory
│   └── tests/                108 tests, including compiling/running the generated firmware
├── frontend/src/
│   ├── app/                  landing page, /studio/[template]
│   ├── components/studio/    parameter & pose panels, insights tabs, wiring diagram, code viewer
│   ├── components/viewport/  Canvas, ArmModel, RoverModel
│   └── lib/                  API client, zustand store, hooks, playback interpolation
└── docker-compose.yml
```

### API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/templates` | Templates, default designs and the parameter UI spec (ranges, units, groups, options from the component library) |
| GET | `/api/components?category=` | Component library |
| POST | `/api/analyze` | Mechanical + electrical analysis of a design |
| POST | `/api/arm/pose` | FK or IK for one pose, with holding torques, centre of mass and warnings |
| POST | `/api/arm/trajectory` | Quintic, limit-respecting trajectory through waypoints (defaults to the pick-and-place demo) |
| POST | `/api/rover/simulate` | Rover motion for a preset program or custom wheel-speed steps |
| POST | `/api/codegen` | Arduino C++ / MicroPython firmware |
| GET/POST/PUT/DELETE | `/api/projects[/{id}]` | Saved designs |

Interactive docs are at `http://localhost:8000/docs`.

### Component library

The parts live in `backend/app/data/components.json` and are upserted into the `components`
table at start-up. To add a part (for example a new servo), add an entry with the same
`specs` keys as its siblings and restart. The selection logic picks it up automatically.
Ratings are typical hobby-market datasheet values; the UI tells users to check the
datasheet of the exact part they buy.

## Testing

```bash
cd backend && pytest && ruff check .
cd frontend && npm run lint && npm run typecheck && npm run build
```

The backend suite covers:

- DH forward kinematics, Jacobians and inertia against closed-form results.
- IK round trips over random poses, and torques against hand calculations.
- Max payload saturating the limiting joint, stability and ballast, and trajectory speed limits.
- Rover force budgets, and paths that close on themselves.
- Every board × driver netlist.
- Firmware parity:
  - The generated **MicroPython** runs against a fake `machine` module, and its IK must match
    the backend's.
  - The generated **Arduino C++** compiles with `g++ -Wall -Wextra -Werror` against stub
    headers for every board and driver. The arm sketch's `solveIK` runs in a harness and
    must match the backend.

## Design decisions and deviations from the architecture doc

- **Kinematics in NumPy instead of Robotics Toolbox / Pinocchio.** The templates are
  small serial chains. A batched DH implementation of about 150 lines covers the whole
  workspace sweep in about 6 ms, keeps the image small, and is easy to verify. Pinocchio
  becomes worthwhile in Phase 3 (arbitrary kinematic trees from URDF).
- **SQLAlchemy** was picked over Prisma so the ORM lives next to the Python engines. Tables
  are created at start-up (`create_all`); add Alembic once the schema starts changing.
- **Some Phase 2 rules are already in.** The MVP auto-inserts regulators, level shifters,
  fuses and capacitors, because the templates are unsafe without them. The drag-and-drop
  schematic editor is still Phase 2.
- **No user accounts yet.** Projects are stored globally. Authentication is the next backend
  item.

## Roadmap from here

- **Phase 2:** an editable schematic canvas, more boards and drivers (PCA9685, BTS7960,
  steppers with A4988), and wire gauge and connector recommendations.
- **Phase 3:** a freeform sandbox that snaps links together, exports URDF, and runs
  kinematics and dynamics on custom trees (Pinocchio). It would also add closed-loop
  control (encoders, PID) to the generated code.
- **Platform:** user accounts, shareable project links, one-click flashing through Web
  Serial.
