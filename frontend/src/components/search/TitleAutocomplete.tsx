"use client";

import { useEffect, useId, useRef, useState } from "react";
import { API_URL } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Suggestion = { title: string; count: number };

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  id?: string;
  className?: string;
  inputClassName?: string;
  name?: string;
};

export function TitleAutocomplete({
  value,
  onChange,
  onSubmit,
  placeholder = "Role, stack, or company",
  id,
  className,
  inputClassName,
  name = "q",
}: Props) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const q = value.trim();
    if (q.length < 2) {
      setItems([]);
      setOpen(false);
      setActive(-1);
      return;
    }
    const t = window.setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/jobs/title-suggestions?q=${encodeURIComponent(q)}&limit=8`,
          { signal: ac.signal, headers: { Accept: "application/json" } },
        );
        if (!res.ok) {
          setItems([]);
          return;
        }
        const data = (await res.json()) as { suggestions?: Suggestion[] };
        setItems(data.suggestions || []);
        setOpen(Boolean(data.suggestions?.length));
        setActive(-1);
      } catch {
        if (!ac.signal.aborted) setItems([]);
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    }, 280);
    return () => window.clearTimeout(t);
  }, [value]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setActive(-1);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function choose(title: string) {
    onChange(title);
    setOpen(false);
    setActive(-1);
    onSubmit?.(title);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setOpen(false);
      setActive(-1);
      return;
    }
    if (!open || !items.length) {
      if (e.key === "Enter") onSubmit?.(value);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i <= 0 ? items.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      if (active >= 0 && items[active]) {
        e.preventDefault();
        choose(items[active].title);
      } else {
        onSubmit?.(value);
      }
    }
  }

  return (
    <div ref={wrapRef} className={cn("relative w-full", className)}>
      <input
        id={id}
        name={name}
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-opt-${active}` : undefined}
        autoComplete="off"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => items.length && setOpen(true)}
        onKeyDown={onKeyDown}
        className={inputClassName}
      />
      {open && items.length ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-40 max-h-72 overflow-auto rounded-lg border border-line bg-elevated py-1 shadow-lift"
        >
          {items.map((s, i) => (
            <li
              key={s.title}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={cn(
                "cursor-pointer px-3 py-2.5 text-sm",
                i === active ? "bg-accent-soft text-ink" : "text-ink hover:bg-paper",
              )}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(s.title);
              }}
            >
              <span className="font-medium">{s.title}</span>
              <span className="ml-2 text-xs text-muted">{s.count} open</span>
            </li>
          ))}
        </ul>
      ) : null}
      {loading && open ? (
        <span className="sr-only" role="status">
          Loading suggestions
        </span>
      ) : null}
    </div>
  );
}
