/**
 * components/MessageBubble.tsx
 *
 * Renders user and assistant messages with glassmorphic cards,
 * copy-to-clipboard, streaming dots, source citations, and confidence badges.
 */

"use client";

import React, { useMemo, useState } from "react";
import clsx from "clsx";
import { Sparkles, User, Copy, Check, AlertCircle } from "lucide-react";
import type { Message } from "@/lib/types";
import LoadingDots from "./LoadingDots";
import ConfidenceBadge from "./ConfidenceBadge";
import SourceCitation from "./SourceCitation";

interface MessageBubbleProps {
  message: Message;
}

/** Apply markdown-like transforms to a string and return JSX */
function renderContent(text: string): React.ReactNode {
  if (!text) return null;

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
        className="my-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 overflow-x-auto text-xs font-mono text-slate-200 shadow-inner"
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
      return (
        <strong key={i} className="font-semibold text-white">
          {seg.slice(2, -2)}
        </strong>
      );
    }
    if (seg.startsWith("`") && seg.endsWith("`")) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded-md bg-slate-800 border border-slate-700/60 text-brand-300 font-mono text-xs"
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
  const [copied, setCopied] = useState(false);
  const rendered = useMemo(() => renderContent(message.content), [message.content]);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={clsx("flex w-full group", isUser ? "justify-end" : "justify-start")}>
      <div className={clsx("flex gap-3 max-w-[85%] md:max-w-[78%]", isUser && "flex-row-reverse")}>
        {/* Avatar */}
        <div
          className={clsx(
            "w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 shadow-md",
            isUser
              ? "bg-slate-800 border border-slate-700 text-slate-300"
              : "bg-gradient-to-tr from-brand-600 to-indigo-600 text-white shadow-brand-500/20"
          )}
        >
          {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
        </div>

        {/* Message Container */}
        <div className={clsx("flex flex-col", isUser ? "items-end" : "items-start")}>
          <div
            className={clsx(
              "relative rounded-2xl px-4 py-3 text-sm leading-relaxed transition-all",
              isUser
                ? "bg-gradient-to-r from-brand-600 to-indigo-600 text-white rounded-tr-sm shadow-lg shadow-brand-600/20 font-normal"
                : "bg-slate-900/90 text-slate-200 rounded-tl-sm border border-slate-800 shadow-md shadow-slate-950/40",
              message.error && "bg-red-950/40 border-red-700/50 text-red-200"
            )}
          >
            {message.error ? (
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <span>Error: {message.error}</span>
              </div>
            ) : (
              <>
                <div className="whitespace-pre-wrap break-words">{rendered}</div>
                {message.isStreaming && <LoadingDots className="mt-2" />}
              </>
            )}

            {/* Quick Action: Copy Button for assistant responses */}
            {!isUser && !message.isStreaming && !message.error && message.content && (
              <button
                onClick={handleCopy}
                className="absolute right-2 top-2 p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-all duration-150"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Sources & Confidence Meta */}
          {!message.isStreaming && !message.error && !isUser && (
            <div className="mt-2 px-1 space-y-1.5 w-full">
              {message.sources && message.sources.length > 0 && (
                <SourceCitation sources={message.sources} />
              )}
              {typeof message.confidence === "number" && (
                <div>
                  <ConfidenceBadge confidence={message.confidence} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
