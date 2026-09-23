import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Studio from "@/components/studio/Studio";

const NAMES = { arm: "3-Axis Arm", rover: "Rover" } as const;

export async function generateMetadata({ params }: PageProps<"/studio/[template]">): Promise<Metadata> {
  const { template } = await params;
  const name = NAMES[template as keyof typeof NAMES];
  return { title: name ? `${name} studio - RoboCraft` : "RoboCraft" };
}

export default async function StudioPage({ params, searchParams }: PageProps<"/studio/[template]">) {
  const { template } = await params;
  if (template !== "arm" && template !== "rover") notFound();
  const { project } = await searchParams;
  return <Studio template={template} projectId={typeof project === "string" ? project : null} />;
}
