// Types mirroring the RoboCraft API (backend/app/schemas).

export type TemplateId = "arm" | "rover";
export type Vec3 = [number, number, number];
export type Severity = "pass" | "info" | "warning" | "error";
export type Language = "arduino" | "micropython";
export type RoverPreset = "square" | "figure8" | "spin";

export interface ParamOption {
  value: string | number;
  label: string;
  note?: string;
}

export interface ParameterSpec {
  key: string;
  kind: "slider" | "select" | "toggle";
  label: string;
  group: string;
  help: string;
  unit: string | null;
  min: number | null;
  max: number | null;
  step: number | null;
  scale: number;
  options: ParamOption[];
}

export interface TemplateSpec {
  id: TemplateId;
  name: string;
  tagline: string;
  description: string;
  defaults: Design;
  groups: string[];
  parameters: ParameterSpec[];
}

export interface ArmDesign {
  template: "arm";
  name: string;
  base_height: number;
  upper_arm_length: number;
  forearm_length: number;
  base_radius: number;
  upper_arm_mass: number;
  forearm_mass: number;
  gripper_mass: number;
  payload_mass: number;
  base_mass: number;
  max_joint_speed: number;
  max_joint_accel: number;
  safety_factor: number;
  board: string;
  power_source: string;
}

export interface RoverDesign {
  template: "rover";
  name: string;
  chassis_length: number;
  chassis_width: number;
  wheel_diameter: number;
  track_width: number;
  drive_motors: 2 | 4;
  chassis_mass: number;
  payload_mass: number;
  max_speed: number;
  max_accel: number;
  max_incline: number;
  surface: string;
  safety_factor: number;
  board: string;
  power_source: string;
  motor_driver: string;
  obstacle_sensor: boolean;
}

export type Design = ArmDesign | RoverDesign;

export interface Check {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  fix: string | null;
  auto_fixed: boolean;
  engine: "mechanical" | "electrical";
}

export interface Part {
  ref: string;
  component_id: string;
  name: string;
  label: string;
  category: string;
  column: number;
  pins: string[];
  auto_added: boolean;
  in_diagram: boolean;
  reason: string;
}

export interface Wire {
  a: string;
  a_pin: string;
  b: string;
  b_pin: string;
  net: string;
  kind: "power" | "ground" | "signal" | "motor";
}

export interface BomItem {
  component_id: string;
  name: string;
  category: string;
  qty: number;
  unit_price_usd: number;
  total_usd: number;
  refs: string[];
  reason: string;
  note: string | null;
  auto_added: boolean;
}

export interface Rail {
  name: string;
  voltage: number;
  source: string;
  typical_a: number;
  peak_a: number;
  capacity_a: number;
  status: "ok" | "warning" | "error";
}

export interface Actuator {
  role: string;
  label: string;
  component_id: string;
  name: string;
  required_nm: number;
  required_kgcm: number;
  available_nm: number;
  available_kgcm: number;
  utilization: number;
  status: "ok" | "marginal" | "insufficient";
  rationale: string;
  alternatives: { component_id: string; name: string; price_usd: number; rating: string }[];
  mass_kg: number;
  price_usd: number;
  extra: Record<string, number | string>;
}

export interface Electrical {
  board: { id: string; name: string; logic_v: number; languages: Language[] };
  actuators: Actuator[];
  parts: Part[];
  wires: Wire[];
  bom: BomItem[];
  rails: Rail[];
  checks: Check[];
  pin_map: Record<string, number>;
  pin_labels: Record<string, string>;
  total_cost_usd: number;
  power_source_id: string;
  driver_id?: string;
  runtime_min?: number;
}

export interface Stability {
  pose_deg: number[];
  com: Vec3;
  total_mass_kg: number;
  horizontal_offset_m: number;
  base_radius_m: number;
  stable: boolean;
  ballast_kg: number;
}

export interface ArmMechanical {
  template: "arm";
  dh_table: {
    joint: number;
    name: string;
    theta: string;
    d: number;
    a: number;
    alpha_deg: number;
    limits_deg: [number, number];
  }[];
  joints: {
    name: string;
    label: string;
    gravity_nm: number;
    inertial_nm: number;
    required_nm: number;
    required_kgcm: number;
    worst_pose_deg: number[];
    limits_deg: [number, number];
  }[];
  reach: { min: number; max: number; shoulder_height: number };
  home_deg: Vec3;
  max_payload_kg: number;
  actuator_masses_kg: Record<string, number>;
  moving_mass_kg: number;
  stability: { home: Stability; extended: Stability };
  checks: Check[];
}

export interface RoverMechanical {
  template: "rover";
  total_mass_kg: number;
  mass_breakdown_kg: Record<string, number>;
  forces_n: { rolling: number; grade: number; acceleration: number; total: number };
  wheel_rpm: number;
  torque_per_motor_nm: number;
  torque_per_motor_kgcm: number;
  power_per_motor_w: number;
  traction: { required_n: number; available_n: number; ok: boolean };
  kinematics: {
    max_yaw_rate_dps: number;
    spin_360_s: number;
    stopping_distance_m: number;
    time_to_top_speed_s: number;
    wheel_circumference_m: number;
    min_turn_radius_m: number;
  };
  motor_top_speed_mps: number;
  obstacle_stop_m: number | null;
  checks: Check[];
}

export interface Summary {
  status: "ok" | "warning" | "error";
  headline: string;
  total_cost_usd: number;
  total_mass_kg: number;
  check_counts: Record<Severity, number>;
  auto_fixes: number;
  servos?: number;
  motors?: number;
  runtime_min?: number;
}

export interface Analysis {
  template: TemplateId;
  name: string;
  mechanical: ArmMechanical | RoverMechanical;
  electrical: Electrical;
  summary: Summary;
}

export interface ArmPose {
  q_deg: Vec3;
  servo_deg: Vec3;
  ee: Vec3;
  joint_positions: Vec3[];
  reachable: boolean;
  within_limits: boolean;
  exact: boolean;
  message: string;
  holding_torque_nm: Vec3;
  com: Vec3;
  stable: boolean;
  warnings: string[];
}

export interface ArmTrajectory {
  duration: number;
  waypoints: {
    label: string;
    gripper: number;
    position: Vec3;
    q_deg: Vec3;
    reachable: boolean;
    t: number;
  }[];
  samples: { t: number; q: Vec3; gripper: number; ee: Vec3 }[];
}

export interface RoverSample {
  t: number;
  x: number;
  y: number;
  heading: number;
  wheel_left: number;
  wheel_right: number;
  v: number;
  omega: number;
}

export interface RoverSim {
  duration: number;
  distance_m: number;
  bounds: { min_x: number; max_x: number; min_y: number; max_y: number };
  steps: { label: string; left: number; right: number; duration: number }[];
  samples: RoverSample[];
  preset: RoverPreset | null;
}

export interface CodegenResult {
  language: Language;
  language_label: string;
  filename: string;
  board: string;
  code: string;
  libraries: string[];
  instructions: string[];
  warnings: string[];
}

export interface Project {
  id: string;
  name: string;
  template: TemplateId;
  design: Design;
  created_at: string;
  updated_at: string;
}
