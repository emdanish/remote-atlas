"use client";

import React, { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText as GSAPSplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, GSAPSplitText, useGSAP);

export interface SplitTextProps {
  text: string;
  className?: string;
  delay?: number;
  duration?: number;
  ease?: string | ((t: number) => number);
  splitType?: "chars" | "words" | "lines" | "words, chars";
  from?: gsap.TweenVars;
  to?: gsap.TweenVars;
  threshold?: number;
  rootMargin?: string;
  tag?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "span";
  textAlign?: React.CSSProperties["textAlign"];
  onLetterAnimationComplete?: () => void;
  /** When false, animate immediately without scroll trigger (hero use). */
  scrollTrigger?: boolean;
}

/**
 * React Bits SplitText — adapted for Remote Atlas:
 * reduced-motion safe, shorter defaults, optional non-scroll hero mode.
 * Full text remains in the DOM for SEO and a11y.
 */
const SplitText: React.FC<SplitTextProps> = ({
  text,
  className = "",
  delay = 40,
  duration = 0.55,
  ease = "power2.out",
  splitType = "words",
  from = { opacity: 0, y: 14 },
  to = { opacity: 1, y: 0 },
  threshold = 0.1,
  rootMargin = "-40px",
  tag = "p",
  textAlign = "left",
  onLetterAnimationComplete,
  scrollTrigger = true,
}) => {
  const ref = useRef<HTMLElement | null>(null);
  const animationCompletedRef = useRef(false);
  const onCompleteRef = useRef(onLetterAnimationComplete);
  const [fontsLoaded, setFontsLoaded] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    onCompleteRef.current = onLetterAnimationComplete;
  }, [onLetterAnimationComplete]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduceMotion(mq.matches);
    const onChange = () => setReduceMotion(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined" || !document.fonts) {
      setFontsLoaded(true);
      return;
    }
    if (document.fonts.status === "loaded") {
      setFontsLoaded(true);
    } else {
      document.fonts.ready.then(() => setFontsLoaded(true));
    }
  }, []);

  useGSAP(
    () => {
      if (!ref.current || !text || !fontsLoaded) return;
      if (animationCompletedRef.current) return;
      if (reduceMotion) {
        animationCompletedRef.current = true;
        onCompleteRef.current?.();
        return;
      }

      const el = ref.current as HTMLElement & {
        _rbsplitInstance?: GSAPSplitText;
      };

      if (el._rbsplitInstance) {
        try {
          el._rbsplitInstance.revert();
        } catch {
          /* noop */
        }
        el._rbsplitInstance = undefined;
      }

      const startPct = (1 - threshold) * 100;
      const marginMatch = /^(-?\d+(?:\.\d+)?)(px|em|rem|%)?$/.exec(rootMargin);
      const marginValue = marginMatch ? parseFloat(marginMatch[1]) : 0;
      const marginUnit = marginMatch ? marginMatch[2] || "px" : "px";
      const sign =
        marginValue === 0
          ? ""
          : marginValue < 0
            ? `-=${Math.abs(marginValue)}${marginUnit}`
            : `+=${marginValue}${marginUnit}`;
      const start = `top ${startPct}%${sign}`;

      let targets: Element[] = [];
      const assignTargets = (self: GSAPSplitText) => {
        if (splitType.includes("chars") && self.chars?.length) targets = self.chars;
        if (!targets.length && splitType.includes("words") && self.words.length)
          targets = self.words;
        if (!targets.length && splitType.includes("lines") && self.lines.length)
          targets = self.lines;
        if (!targets.length) targets = self.chars || self.words || self.lines;
      };

      const splitInstance = new GSAPSplitText(el, {
        type: splitType,
        smartWrap: true,
        autoSplit: splitType === "lines",
        linesClass: "split-line",
        wordsClass: "split-word",
        charsClass: "split-char",
        reduceWhiteSpace: false,
        onSplit: (self: GSAPSplitText) => {
          assignTargets(self);
          return gsap.fromTo(
            targets,
            { ...from },
            {
              ...to,
              duration,
              ease,
              stagger: delay / 1000,
              ...(scrollTrigger
                ? {
                    scrollTrigger: {
                      trigger: el,
                      start,
                      once: true,
                      fastScrollEnd: true,
                      anticipatePin: 0.4,
                    },
                  }
                : {}),
              onComplete: () => {
                animationCompletedRef.current = true;
                onCompleteRef.current?.();
              },
              willChange: "transform, opacity",
              force3D: true,
            },
          );
        },
      });
      el._rbsplitInstance = splitInstance;
      return () => {
        ScrollTrigger.getAll().forEach((st) => {
          if (st.trigger === el) st.kill();
        });
        try {
          splitInstance.revert();
        } catch {
          /* noop */
        }
        el._rbsplitInstance = undefined;
      };
    },
    {
      dependencies: [
        text,
        delay,
        duration,
        ease,
        splitType,
        JSON.stringify(from),
        JSON.stringify(to),
        threshold,
        rootMargin,
        fontsLoaded,
        reduceMotion,
        scrollTrigger,
      ],
      scope: ref,
    },
  );

  const style: React.CSSProperties = {
    textAlign,
    wordWrap: "break-word",
  };
  const classes = `split-parent whitespace-normal ${className}`;
  const Tag = (tag || "p") as React.ElementType;

  return (
    <Tag ref={ref} style={style} className={classes}>
      {text}
    </Tag>
  );
};

export default SplitText;
