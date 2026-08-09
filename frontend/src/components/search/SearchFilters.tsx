"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { TitleAutocomplete } from "@/components/search/TitleAutocomplete";
import { cn } from "@/lib/utils";
import {
  catalogTechsExcluding,
  formatTechLabel,
  normalizeTechValue,
  recommendedTechsFromProfile,
} from "@/lib/techCatalog";

export type SearchFilterState = {
  q: string;
  workplace: string;
  career_stage: string;
  city: string;
  country: string;
  company: string;
  employment_type: string;
  posted_within: string;
  skills: string;
  source: string;
  pakistan_friendly: boolean;
  hybrid: boolean;
};

const workplaces = [
  { value: "", label: "Any workplace" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

const stages = [
  { value: "", label: "Any experience" },
  { value: "internship", label: "Internship" },
  { value: "junior", label: "Junior / Entry" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
  { value: "unknown", label: "Not specified" },
];

const sources = [
  { value: "", label: "All sources" },
  { value: "greenhouse", label: "Greenhouse" },
  { value: "ashby", label: "Ashby" },
  { value: "lever", label: "Lever" },
  { value: "bamboohr", label: "BambooHR" },
  { value: "himalayas", label: "Himalayas" },
  { value: "smartrecruiters", label: "SmartRecruiters" },
  { value: "themuse", label: "The Muse" },
  { value: "weworkremotely", label: "We Work Remotely" },
  { value: "remotejobsorg", label: "RemoteJobs.org" },
  { value: "remoteok", label: "RemoteOK" },
  { value: "arbeitnow", label: "Arbeitnow" },
  { value: "remotive", label: "Remotive" },
  { value: "jobicy", label: "Jobicy" },
  { value: "recruitee", label: "Recruitee" },
  { value: "personio", label: "Personio" },
  { value: "teamtailor", label: "Teamtailor" },
  { value: "workable", label: "Workable" },
  { value: "breezy", label: "Breezy" },
  { value: "workday", label: "Workday" },
];

// Cap aligns with backend FRESHNESS_DAYS (30).
const dates = [
  { value: "1", label: "Last 24 hours" },
  { value: "3", label: "Last 3 days" },
  { value: "7", label: "Last 7 days" },
  { value: "14", label: "Last 14 days" },
  { value: "30", label: "Last 30 days" },
];

const employmentTypes = [
  { value: "", label: "Any employment" },
  { value: "full", label: "Full-time" },
  { value: "part", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "intern", label: "Internship" },
];

type Props = {
  value: SearchFilterState;
  onChange: (next: SearchFilterState) => void;
  onSubmit: () => void;
  onClear: () => void;
  /** From profile / resume */
  profileSkills?: string[];
  profileTechnologies?: string[];
  compact?: boolean;
};

function ChipButton({
  label,
  on,
  onClick,
}: {
  label: string;
  on: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={cn(
        "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
        on
          ? "border-accent bg-accent-soft text-accent-strong"
          : "border-line bg-elevated text-muted hover:border-ink/20 hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}

function parseSkills(skills: string): string[] {
  return skills
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function SearchFilters({
  value,
  onChange,
  onSubmit,
  onClear,
  profileSkills = [],
  profileTechnologies = [],
  compact,
}: Props) {
  const [customTech, setCustomTech] = useState("");

  const set = <K extends keyof SearchFilterState>(key: K, v: SearchFilterState[K]) =>
    onChange({ ...value, [key]: v });

  const skillParts = parseSkills(value.skills);
  const activeSkills = skillParts.map((s) => s.toLowerCase());

  const toggleSkill = (skill: string) => {
    const normalized = normalizeTechValue(skill) || skill.trim();
    if (!normalized) return;
    const lower = normalized.toLowerCase();
    const exists = skillParts.some((p) => p.toLowerCase() === lower);
    const next = exists
      ? skillParts.filter((p) => p.toLowerCase() !== lower)
      : [...skillParts, normalized];
    set("skills", next.join(", "));
  };

  const addCustomTech = () => {
    const raw = customTech.trim();
    if (!raw) return;
    // Support comma-separated multi-add
    const pieces = raw.split(",").map((s) => s.trim()).filter(Boolean);
    let parts = [...skillParts];
    for (const p of pieces) {
      const v = normalizeTechValue(p) || p;
      if (!parts.some((x) => x.toLowerCase() === v.toLowerCase())) {
        parts = [...parts, v];
      }
    }
    set("skills", parts.join(", "));
    setCustomTech("");
  };

  const recommended = recommendedTechsFromProfile(profileSkills, profileTechnologies);
  const catalog = catalogTechsExcluding(recommended);
  const extraSelected = activeSkills.filter(
    (s) =>
      !recommended.some((r) => r.value === s) && !catalog.some((c) => c.value === s),
  );

  return (
    <form
      className={cn("space-y-5", compact && "space-y-3")}
      onSubmit={(e) => {
        e.preventDefault();
        if (customTech.trim()) addCustomTech();
        onSubmit();
      }}
    >
      <div>
        <label htmlFor="q" className="mb-1.5 block text-sm font-medium text-ink">
          Search
        </label>
        <TitleAutocomplete
          id="q"
          name="q"
          value={value.q}
          onChange={(q) => set("q", q)}
          onSubmit={() => onSubmit()}
          placeholder='e.g. “Senior React engineer”, “Python backend”, or “data engineer”'
          inputClassName="flex h-10 w-full rounded-md border border-line bg-elevated px-3 text-sm text-ink outline-none ring-accent placeholder:text-muted focus:ring-2"
        />
      </div>

      <div className={cn("grid gap-3", compact ? "sm:grid-cols-2 lg:grid-cols-4" : "grid-cols-1")}>
        <Field label="Date posted">
          <Select value={value.posted_within} onChange={(v) => set("posted_within", v)} options={dates} />
        </Field>
        <Field label="Workplace">
          <Select value={value.workplace} onChange={(v) => set("workplace", v)} options={workplaces} />
        </Field>
        <Field label="Experience">
          <Select value={value.career_stage} onChange={(v) => set("career_stage", v)} options={stages} />
        </Field>
        <Field label="City / region">
          <Input
            value={value.city}
            onChange={(e) => set("city", e.target.value)}
            placeholder="e.g. Lahore, Berlin, or London"
          />
        </Field>
        <Field label="Country">
          <Input
            value={value.country}
            onChange={(e) => set("country", e.target.value)}
            placeholder="e.g. Pakistan, Germany, or United States"
          />
        </Field>
        <Field label="Company">
          <Input
            value={value.company}
            onChange={(e) => set("company", e.target.value)}
            placeholder="e.g. Stripe, Shopify, or Coupa"
          />
        </Field>
        <Field label="Employment">
          <Select
            value={value.employment_type}
            onChange={(v) => set("employment_type", v)}
            options={employmentTypes}
          />
        </Field>
        <Field label="Source">
          <Select value={value.source} onChange={(v) => set("source", v)} options={sources} />
        </Field>
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-ink">Technologies</legend>

        {recommended.length > 0 ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-accent">
              From your profile / resume
            </p>
            <div className="flex flex-wrap gap-1.5">
              {recommended.map((chip) => (
                <ChipButton
                  key={`rec-${chip.value}`}
                  label={chip.label}
                  on={activeSkills.includes(chip.value)}
                  onClick={() => toggleSkill(chip.value)}
                />
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted">
            Upload a resume on onboarding or Matches for personalised tech chips you can tap. Nothing
            is auto-selected on Jobs until you choose chips yourself.
          </p>
        )}

        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
            Browse catalogue
          </p>
          <div className="flex max-h-36 flex-wrap gap-1.5 overflow-y-auto atlas-scroll pr-1">
            {catalog.map((chip) => (
              <ChipButton
                key={`cat-${chip.value}`}
                label={chip.label}
                on={activeSkills.includes(chip.value)}
                onClick={() => toggleSkill(chip.value)}
              />
            ))}
          </div>
        </div>

        {(skillParts.length > 0 || extraSelected.length > 0) && (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">Selected</p>
            <ul className="flex flex-wrap gap-1.5">
              {skillParts.map((s, i) => (
                <li key={`${s.toLowerCase()}-${i}`}>
                  <button
                    type="button"
                    onClick={() => toggleSkill(s)}
                    className="inline-flex items-center gap-1 rounded-md border border-accent/40 bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-strong"
                  >
                    {formatTechLabel(s)}
                    <X className="h-3 w-3" aria-hidden />
                    <span className="sr-only">Remove {s}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <label htmlFor="custom-tech" className="mb-1.5 block text-sm font-medium text-ink">
            Add any tech
          </label>
          <div className="flex gap-2">
            <Input
              id="custom-tech"
              value={customTech}
              onChange={(e) => setCustomTech(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustomTech();
                }
              }}
              placeholder="e.g. Docker, Kafka, Elixir — press Enter to add"
              aria-label="Add technology not in list"
            />
            <Button type="button" variant="secondary" size="sm" onClick={addCustomTech}>
              Add
            </Button>
          </div>
          <span className="mt-1 block text-xs text-muted">
            Not limited to chips. Press Enter or Add.
          </span>
        </div>
      </fieldset>

      <div className="space-y-3 rounded-lg border border-line bg-paper/70 p-3">
        <label className="flex items-start gap-3 text-sm text-ink">
          <input
            type="checkbox"
            checked={value.pakistan_friendly}
            onChange={(e) => set("pakistan_friendly", e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-line accent-accent"
          />
          <span>
            <span className="block font-medium">Pakistan-friendly</span>
            <span className="mt-0.5 block text-xs leading-relaxed text-muted">
              Remote roles likely open to applicants in Pakistan.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-3 border-t border-line pt-3 text-sm text-ink">
          <input
            type="checkbox"
            checked={value.hybrid}
            onChange={(e) => set("hybrid", e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-line accent-accent"
          />
          <span>
            <span className="block font-medium">Meaning-aware ranking</span>
            <span className="mt-0.5 block text-xs leading-relaxed text-muted">
              When sort is “Best match”, combine keyword + semantic relevance if available.
            </span>
          </span>
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" className="min-w-[7rem]">
          Apply filters
        </Button>
        <Button type="button" variant="ghost" onClick={onClear}>
          Clear
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-line bg-elevated px-3 py-2 text-sm text-ink outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
    >
      {options.map((o) => (
        <option key={o.value || "any"} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
