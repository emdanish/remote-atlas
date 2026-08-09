"use client";

import SplitText from "@/components/SplitText";

/**
 * Client island for the landing H1. Text is present in HTML for SEO/crawlers;
 * animation only runs when motion is allowed.
 */
export function HeroHeadline({ text }: { text: string }) {
  return (
    <SplitText
      text={text}
      tag="h1"
      splitType="words"
      delay={45}
      duration={0.5}
      ease="power2.out"
      from={{ opacity: 0, y: 18 }}
      to={{ opacity: 1, y: 0 }}
      textAlign="left"
      scrollTrigger={false}
      className="max-w-3xl font-display text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-balance text-white sm:text-5xl lg:text-6xl"
    />
  );
}
