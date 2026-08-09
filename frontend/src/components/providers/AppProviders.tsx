"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion, domAnimation } from "motion/react";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { useState, type ReactNode } from "react";
import { ToastProvider } from "@/components/ui/Toaster";
import { AuthProvider } from "@/lib/auth";

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <NuqsAdapter>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <ToastProvider>
            <LazyMotion features={domAnimation} strict>
              {children}
            </LazyMotion>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </NuqsAdapter>
  );
}
