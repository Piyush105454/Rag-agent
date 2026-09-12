/**
 * components/LoadingDots.tsx
 *
 * Animated three-dot loading indicator shown while an assistant message
 * is being streamed. Uses Tailwind keyframe animation defined in
 * tailwind.config.js (bounceDot) with staggered delays per dot.
 */

"use client";

import React from "react";
import clsx from "clsx";

interface LoadingDotsProps {
  /** Optional extra class for the container */
  className?: string;
}

export default function LoadingDots({ className }: LoadingDotsProps) {
  return (
    <span
      className={clsx("inline-flex items-end gap-0.5 h-4", className)}
      aria-label="Loading response..."
      role="status"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block w-1.5 h-1.5 rounded-full bg-brand-400"
          style={{
            animation: "bounceDot 1.2s ease-in-out infinite",
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </span>
  );
}
