"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastTone = "success" | "error" | "info";

type ToastItem = {
  id: number;
  tone: ToastTone;
  title?: string;
  message: string;
};

type ToastApi = {
  push: (message: string, opts?: { tone?: ToastTone; title?: string }) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

const tones: Record<
  ToastTone,
  { box: string; icon: string; Icon: typeof CheckCircle2 }
> = {
  success: {
    box: "border-emerald-600/25 bg-emerald-50 text-emerald-950",
    icon: "text-emerald-700",
    Icon: CheckCircle2,
  },
  error: {
    box: "border-danger/25 bg-red-50 text-danger",
    icon: "text-danger",
    Icon: AlertCircle,
  },
  info: {
    box: "border-line bg-elevated text-ink",
    icon: "text-accent",
    Icon: Info,
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, opts?: { tone?: ToastTone; title?: string }) => {
      const id = Date.now() + Math.floor(Math.random() * 1000);
      const tone = opts?.tone || "info";
      setItems((prev) => [...prev.slice(-4), { id, tone, title: opts?.title, message }]);
      window.setTimeout(() => dismiss(id), 4200);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (message, title = "Saved") => push(message, { tone: "success", title }),
      error: (message, title = "Something went wrong") =>
        push(message, { tone: "error", title }),
      info: (message, title) => push(message, { tone: "info", title }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
        aria-live="polite"
        aria-relevant="additions"
      >
        {items.map((t) => {
          const conf = tones[t.tone];
          const Icon = conf.Icon;
          return (
            <div
              key={t.id}
              role="status"
              className={cn(
                "pointer-events-auto flex w-full max-w-sm gap-3 rounded-xl border px-3.5 py-3 shadow-lift sm:px-4",
                conf.box,
              )}
            >
              <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", conf.icon)} aria-hidden />
              <div className="min-w-0 flex-1 text-sm leading-snug">
                {t.title ? <p className="font-semibold">{t.title}</p> : null}
                <p className={t.title ? "mt-0.5 opacity-90" : ""}>{t.message}</p>
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="shrink-0 rounded-md p-1 opacity-60 transition hover:bg-ink/5 hover:opacity-100"
                aria-label="Dismiss notification"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Safe no-op outside provider (SSR / edge cases)
    return {
      push: () => undefined,
      success: () => undefined,
      error: () => undefined,
      info: () => undefined,
    };
  }
  return ctx;
}
