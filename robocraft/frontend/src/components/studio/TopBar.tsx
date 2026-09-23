"use client";

import { ArrowLeft, Check, FileJson, LoaderCircle, Save } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { isDirty, useStudio } from "@/lib/store";
import { Badge, Button } from "../ui";
import Logo from "../Logo";
import { download } from "./ElectronicsTab";

export default function TopBar() {
  const design = useStudio((s) => s.design);
  const spec = useStudio((s) => s.spec);
  const projectId = useStudio((s) => s.projectId);
  const dirty = useStudio(isDirty);
  const setName = useStudio((s) => s.setName);
  const markSaved = useStudio((s) => s.markSaved);
  const status = useStudio((s) => s.analysis?.summary.status);
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const save = async () => {
    if (!design) return;
    setSaving(true);
    setSaveError(null);
    try {
      const project = projectId
        ? await api.updateProject(projectId, design.name, design)
        : await api.createProject(design.name, design);
      markSaved(project.id);
      if (!projectId) router.replace(`/studio/${design.template}?project=${project.id}`, { scroll: false });
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-ink-800 bg-ink-950/90 px-3 backdrop-blur sm:px-4">
      <Link
        href="/"
        className="flex items-center gap-2 text-ink-300 hover:text-ink-100"
        aria-label="Back to home"
      >
        <ArrowLeft className="size-4" />
        <Logo className="size-6" />
      </Link>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <input
          aria-label="Project name"
          value={design?.name ?? ""}
          onChange={(e) => setName(e.target.value)}
          maxLength={80}
          className="max-w-64 min-w-0 flex-1 truncate rounded-md border border-transparent bg-transparent px-1.5 py-1 text-sm font-semibold hover:border-ink-700 focus:border-brand-500 focus:outline-none"
        />
        {spec && <Badge className="max-sm:hidden">{spec.name}</Badge>}
        {status && (
          <Badge
            tone={status === "ok" ? "ok" : status === "warning" ? "warn" : "error"}
            className="max-md:hidden"
          >
            {status === "ok" ? "feasible" : status === "warning" ? "warnings" : "needs fixes"}
          </Badge>
        )}
      </div>
      {saveError && <span className="hidden text-xs text-red-300 lg:inline">{saveError}</span>}
      <Button
        variant="ghost"
        size="sm"
        onClick={() =>
          design &&
          download(
            `${design.name.replace(/\s+/g, "_")}.robocraft.json`,
            JSON.stringify(design, null, 2),
            "application/json",
          )
        }
        title="Download the design as JSON"
      >
        <FileJson className="size-3.5" /> <span className="hidden sm:inline">Export</span>
      </Button>
      <Button
        variant={dirty || !projectId ? "primary" : "secondary"}
        size="sm"
        onClick={save}
        disabled={saving || !design}
      >
        {saving ? (
          <LoaderCircle className="size-3.5 animate-spin" />
        ) : !dirty && projectId ? (
          <Check className="size-3.5" />
        ) : (
          <Save className="size-3.5" />
        )}
        {!dirty && projectId ? "Saved" : "Save"}
      </Button>
    </header>
  );
}
