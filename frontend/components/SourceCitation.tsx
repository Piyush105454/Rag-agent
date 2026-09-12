/**
 * components/SourceCitation.tsx
 *
 * Renders inline source citation chips for assistant messages.
 * Each chip shows the filename (truncated) and page number as
 * a clickable pill. Clicking a chip is a no-op today but the
 * onClick prop is wired up for future document preview support.
 */

"use client";

import React from "react";
import clsx from "clsx";
import type { Source } from "@/lib/types";

interface SourceCitationProps {
  sources: Source[];
  /** Optional click handler for future doc preview */
  onSourceClick?: (source: Source) => void;
}

function truncateFilename(filename: string, maxLen = 24): string {
  if (filename.length <= maxLen) return filename;
  const ext = filename.lastIndexOf(".");
  if (ext > 0) {
    const name = filename.slice(0, ext);
    const extension = filename.slice(ext);
    const half = maxLen - extension.length - 3;
    return `${name.slice(0, half)}...${extension}`;
  }
  return `${filename.slice(0, maxLen - 3)}...`;
}

export default function SourceCitation({
  sources,
  onSourceClick,
}: SourceCitationProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2" aria-label="Sources">
      <span className="text-xs text-slate-500 self-center">Sources:</span>
      {sources.map((source) => (
        <button
          key={source.chunk_id}
          onClick={() => onSourceClick?.(source)}
          className={clsx(
            "inline-flex items-center gap-1 px-2 py-0.5",
            "rounded-full border border-slate-600/60",
            "bg-slate-800/60 hover:bg-slate-700/60",
            "text-xs text-slate-300 hover:text-slate-100",
            "transition-colors duration-150 cursor-pointer",
            "max-w-[200px]"
          )}
          title={`${source.file}, page ${source.page}`}
          aria-label={`Source: ${source.file}, page ${source.page}`}
        >
          <svg
            className="w-3 h-3 text-brand-400 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="truncate">{truncateFilename(source.file)}</span>
          <span className="flex-shrink-0 text-slate-500">p.{source.page}</span>
        </button>
      ))}
    </div>
  );
}
