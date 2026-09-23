"use client";

import { Bot, Car, FolderOpen, LoaderCircle, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "./ui";

export default function SavedProjects() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .projects()
      .then(setProjects)
      .catch((err: Error) => setError(err.message));
  }, []);

  const remove = async (id: string) => {
    await api.deleteProject(id);
    setProjects((list) => list?.filter((p) => p.id !== id) ?? null);
  };

  if (error) {
    return (
      <p className="rounded-xl border border-dashed border-ink-800 p-5 text-sm text-ink-400">
        {error} Saved projects will appear here once the API is running.
      </p>
    );
  }
  if (!projects) {
    return (
      <p className="flex items-center gap-2 text-sm text-ink-400">
        <LoaderCircle className="size-4 animate-spin" /> Loading projects…
      </p>
    );
  }
  if (projects.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-ink-800 p-5 text-sm text-ink-400">
        No saved projects yet. Start from a template above and press <b>Save</b> in the studio.
      </p>
    );
  }
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((p) => {
        const Icon = p.template === "arm" ? Bot : Car;
        return (
          <li
            key={p.id}
            className="flex items-center gap-3 rounded-xl border border-ink-800 bg-ink-900/60 p-3 transition-colors hover:border-ink-600"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-ink-800 text-brand-300">
              <Icon className="size-4.5" />
            </span>
            <Link href={`/studio/${p.template}?project=${p.id}`} className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{p.name}</div>
              <div className="text-[11px] text-ink-400">
                {p.template === "arm" ? "3-axis arm" : "Rover"} · updated{" "}
                {new Date(p.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </div>
            </Link>
            <Link href={`/studio/${p.template}?project=${p.id}`} aria-label={`Open ${p.name}`}>
              <Button size="sm" variant="ghost">
                <FolderOpen className="size-3.5" />
              </Button>
            </Link>
            <Button size="sm" variant="danger" onClick={() => remove(p.id)} aria-label={`Delete ${p.name}`}>
              <Trash2 className="size-3.5" />
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
