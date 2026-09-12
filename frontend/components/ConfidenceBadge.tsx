/**
 * components/ConfidenceBadge.tsx
 *
 * Visual indicator for answer confidence score.
 * Renders a small pill badge colored:
 *   - Green  (>0.7)  — high confidence, answer is well-supported
 *   - Yellow (0.4–0.7) — moderate confidence, some uncertainty
 *   - Red    (<0.4)  — low confidence, answer may be unreliable
 */

"use client";

import React from "react";
import clsx from "clsx";

interface ConfidenceBadgeProps {
  /** Confidence score between 0 and 1 */
  confidence: number;
}

function getLabel(confidence: number): string {
  if (confidence > 0.7) return "High confidence";
  if (confidence >= 0.4) return "Moderate confidence";
  return "Low confidence";
}

function getColorClasses(confidence: number): string {
  if (confidence > 0.7)
    return "bg-emerald-900/60 text-emerald-300 border-emerald-700/50";
  if (confidence >= 0.4)
    return "bg-yellow-900/60 text-yellow-300 border-yellow-700/50";
  return "bg-red-900/60 text-red-300 border-red-700/50";
}

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);
  const label = getLabel(confidence);
  const colorClasses = getColorClasses(confidence);

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full",
        "text-xs font-medium border",
        colorClasses
      )}
      title={label}
      aria-label={`${label}: ${pct}%`}
    >
      <span
        className={clsx("w-1.5 h-1.5 rounded-full", {
          "bg-emerald-400": confidence > 0.7,
          "bg-yellow-400": confidence >= 0.4 && confidence <= 0.7,
          "bg-red-400": confidence < 0.4,
        })}
      />
      {pct}% confidence
    </span>
  );
}
