import type { Metadata } from "next";
import { SkillSeoLanding, skillSeoMetadata } from "@/components/seo/SkillSeoLanding";

export const revalidate = 1800;

type Props = {
  params: Promise<{ skill: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { skill } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const meta = await skillSeoMetadata(skill.toLowerCase());
  if (page > 1) {
    return { ...meta, robots: { index: false, follow: true } };
  }
  return meta;
}

export default async function SkillSeoPage({ params, searchParams }: Props) {
  const { skill } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  return <SkillSeoLanding skill={skill.toLowerCase()} page={page} />;
}
