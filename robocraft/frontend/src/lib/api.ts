import type {
  Analysis,
  ArmPose,
  ArmTrajectory,
  CodegenResult,
  Design,
  Language,
  Project,
  RoverPreset,
  RoverSim,
  TemplateSpec,
  Vec3,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the RoboCraft engine. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
            : detail;
    } catch {
      /* keep statusText */
    }
    if (res.status >= 500 && res.status !== 502) detail = `Engine error: ${detail}`;
    if (res.status === 502 || res.status === 503 || res.status === 504)
      detail = "Can't reach the RoboCraft engine. Is the backend running?";
    throw new ApiError(detail, res.status);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

export const api = {
  templates: () => request<TemplateSpec[]>("/api/templates"),
  analyze: (design: Design, signal?: AbortSignal) => post<Analysis>("/api/analyze", { design }, signal),
  armPose: (
    body: {
      design: Design;
      mode: "ik" | "fk";
      target?: Vec3;
      joints?: Vec3;
      current?: Vec3;
      actuator_masses_kg?: Record<string, number>;
    },
    signal?: AbortSignal,
  ) => post<ArmPose>("/api/arm/pose", body, signal),
  armTrajectory: (design: Design, signal?: AbortSignal) =>
    post<ArmTrajectory>("/api/arm/trajectory", { design }, signal),
  roverSimulate: (design: Design, preset: RoverPreset, signal?: AbortSignal) =>
    post<RoverSim>("/api/rover/simulate", { design, preset }, signal),
  codegen: (design: Design, language: Language, preset: RoverPreset, signal?: AbortSignal) =>
    post<CodegenResult>("/api/codegen", { design, language, preset }, signal),
  projects: () => request<Project[]>("/api/projects"),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (name: string, design: Design) => post<Project>("/api/projects", { name, design }),
  updateProject: (id: string, name: string, design: Design) =>
    request<Project>(`/api/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name, design }),
    }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
};

export const isAbort = (err: unknown) => (err as Error)?.name === "AbortError";
