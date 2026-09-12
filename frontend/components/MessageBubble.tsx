/**
 * components/MessageBubble.tsx
 *
 * Renders a single message in the chat thread.
 * User messages are right-aligned with a blue background.
 * Assistant messages are left-aligned with a dark surface background.
 * During streaming, a LoadingDots indicator is shown after the content.
 * After streaming completes, SourceCitation chips and ConfidenceBadge appear.
 * If an error occurred, a red error box is rendered instead.
 *
 * Basic markdown-like formatting is applied:
 *   - **bold** → <strong>
 *   - `code` → <code>
 *   - ```...``` → <pre><code> blocks
 * This avoids adding a full markdown parser dependency.
 */

"use client";

import React, { useMemo } from "react";
import clsx from "clsx";
import type { Message } from "@/lib/types";
import LoadingDots from "./LoadingDots";
import ConfidenceBadge from "./ConfidenceBadge";
import SourceCitation from "./SourceCitation";

interface MessageBubbleProps {
  message: Message;
}

/** Apply simple markdown-like transforms to a string and return JSX */
function renderContent(text: string): React.ReactNode {
  if (!text) return null;

  // Split on triple-backtick code blocks first
  const codeBlockRegex = /```[\w]*\n?([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    const before = text.slice(lastIndex, match.index);
    if (before) parts.push(<span key={key++}>{renderInline(before)}</span>);
    parts.push(
      <pre
        key={key++}
        className="my-2 p-3 rounded-lg bg-slate-950 border border-slate-700 overflow-x-auto text-sm font-mono text-slate-200"
      >
        <code>{match[1]?.trim()}</code>
      </pre>
    );
    lastIndex = match.index + match[0].length;
  }

  const remaining = text.slice(lastIndex);
  if (remaining) parts.push(<span key={key++}>{renderInline(remaining)}</span>);

  return <>{parts}</>;
}

/** Render inline markdown: **bold**, `code`, line breaks */
function renderInline(text: string): React.ReactNode {
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\n)/g);
  return segments.map((seg, i) => {
    if (seg.startsWith("**") && seg.endsWith("**")) {
      return <strong key={i} className="font-semibold text-slate-100">{seg.slice(2, -2)}</strong>;
    }
    if (seg.startsWith("`") && seg.endsWith("`")) {
      return (
        <code
          key={i}
          className="px-1 py-0.5 rounded bg-slate-900 border border-slate-700 text-brand-300 font-mono text-sm"
        >
          {seg.slice(1, -1)}
        </code>
      );
    }
    if (seg === "\n") {
      return <br key={i} />;
    }
    return seg;
  });
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const rendered = useMemo(() => renderContent(message.content), [message.content]);

  return (
    <div
      className={clsx(
        "flex w-full mb-4 px-4",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* Avatar — assistant only */}
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-700 flex items-center justify-center mr-3 mt-1">
          <svg className="w-4 h-4 text-brand-200" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z" />
          </svg>
        </div>
      )}

      <div className={clsx("flex flex-col max-w-[75%]", isUser && "items-end")}>
        {/* Bubble */}
        <div
          className={clsx(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-brand-600 text-white rounded-br-sm"
              : "bg-slate-800 text-slate-200 rounded-bl-sm border border-slate-700/50",
            message.error && "bg-red-900/30 border-red-700/50 text-red-200"
          )}
        >
          {message.error ? (
            <div className="flex items-start gap-2">
              <svg className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span>Error: {message.error}</span>
            </div>
          ) : (
            <>
              <div className="whitespace-pre-wrap break-words">{rendered}</div>
              {message.isStreaming && (
                <LoadingDots className="mt-1.5" />
              )}
            </>
          )}
        </div>

        {/* Sources + Confidence — shown after streaming ends */}
        {!message.isStreaming && !message.error && !isUser && (
          <div className="mt-1.5 px-1">
            {message.sources && message.sources.length > 0 && (
              <SourceCitation sources={message.sources} />
            )}
            {typeof message.confidence === "number" && (
              <div className="mt-1.5">
                <ConfidenceBadge confidence={message.confidence} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Avatar — user only */}
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center ml-3 mt-1">
          <svg className="w-4 h-4 text-slate-200" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
          </svg>
        </div>
      )}
    </div>
  );
}
