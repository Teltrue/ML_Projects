"use client";

import { LoaderCircle, ServerCrash } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAnalysis, useArmPose, useCodegen } from "@/lib/hooks";
import { useStudio } from "@/lib/store";
import { useMediaQuery } from "@/lib/useMediaQuery";
import type { Design, TemplateId } from "@/lib/types";
import { Button, Segmented } from "../ui";
import Insights from "./Insights";
import ParamPanel from "./ParamPanel";
import PosePanel from "./PosePanel";
import TopBar from "./TopBar";
import { PlaybackBar, ViewToggles } from "./ViewportOverlay";

const Viewport = dynamic(() => import("../viewport/Viewport"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center gap-2 text-sm text-ink-400">
      <LoaderCircle className="size-4 animate-spin" /> Loading 3D engine…
    </div>
  ),
});

function DesignControls({ template }: { template: TemplateId }) {
  return (
    <>
      {template === "arm" && <PosePanel />}
      <ParamPanel />
    </>
  );
}

export default function Studio({ template, projectId }: { template: TemplateId; projectId: string | null }) {
  const ready = useStudio((s) => s.spec?.id === template && s.design !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [mobilePane, setMobilePane] = useState<"design" | "results">("design");
  const desktop = useMediaQuery("(min-width: 1024px)");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const templates = await api.templates();
        const spec = templates.find((t) => t.id === template);
        if (!spec) throw new Error(`Unknown template '${template}'`);
        let design: Design = spec.defaults;
        let id: string | null = null;
        if (projectId) {
          const project = await api.project(projectId);
          if (project.template === template) {
            design = { ...spec.defaults, ...project.design } as Design;
            id = project.id;
          }
        }
        if (!cancelled) {
          setLoadError(null);
          useStudio.getState().init(spec, design, id);
        }
      } catch (err) {
        if (!cancelled) setLoadError((err as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [template, projectId, attempt]);

  useAnalysis();
  useArmPose();
  useCodegen();

  if (loadError) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <ServerCrash className="size-10 text-red-300" />
        <div>
          <h1 className="text-lg font-semibold">Can&apos;t start the studio</h1>
          <p className="mt-1 max-w-md text-sm text-ink-400">{loadError}</p>
          <p className="mt-3 text-xs text-ink-400">
            Start the API with <code className="rounded bg-ink-800 px-1.5 py-0.5">uvicorn app.main:app</code>{" "}
            in <code className="rounded bg-ink-800 px-1.5 py-0.5">robocraft/backend</code>.
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setAttempt((a) => a + 1)}>Retry</Button>
          <Link href="/">
            <Button variant="ghost">Home</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-ink-400">
        <LoaderCircle className="size-4 animate-spin" /> Preparing your workspace…
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {desktop && (
          <aside className="rc-scroll w-[300px] shrink-0 overflow-y-auto border-r border-ink-800 bg-ink-950">
            <DesignControls template={template} />
          </aside>
        )}

        <main className="rc-grid-bg relative h-[44vh] shrink-0 border-b border-ink-800 lg:h-auto lg:min-w-0 lg:flex-1 lg:border-b-0">
          <Viewport />
          <div className="pointer-events-none absolute inset-x-3 top-3 flex justify-end">
            <ViewToggles />
          </div>
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex justify-center">
            <div className="w-full max-w-xl">
              <PlaybackBar />
            </div>
          </div>
        </main>

        <aside className="flex min-h-0 flex-1 flex-col border-ink-800 bg-ink-950 lg:w-[420px] lg:flex-none lg:border-l xl:w-[460px]">
          {desktop ? (
            <Insights />
          ) : (
            <>
              <div className="flex justify-center border-b border-ink-800 p-2">
                <Segmented
                  value={mobilePane}
                  onChange={setMobilePane}
                  options={[
                    { value: "design", label: "Design" },
                    { value: "results", label: "Results" },
                  ]}
                />
              </div>
              <div className="rc-scroll min-h-0 flex-1 overflow-y-auto">
                {mobilePane === "design" ? <DesignControls template={template} /> : <Insights />}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
