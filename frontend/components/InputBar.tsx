/**
 * components/InputBar.tsx
 *
 * Modern floating dock input bar for submitting RAG queries.
 * Features auto-expanding textarea, keyboard shortcuts, and glowing send state.
 */

"use client";

import React, {
  useState,
  useRef,
  useEffect,
  KeyboardEvent,
  useCallback,
} from "react";
import clsx from "clsx";
import { ArrowUp, CornerDownLeft } from "lucide-react";

interface InputBarProps {
  onSend: (question: string) => void;
  disabled: boolean;
}

const MAX_HEIGHT = 200; // px

export default function InputBar({ onSend, disabled }: InputBarProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  // Listen for suggestion clicks from ChatWindow empty state
  useEffect(() => {
    const handler = (e: Event) => {
      const suggestion = (e as CustomEvent<string>).detail;
      setValue(suggestion);
      textareaRef.current?.focus();
    };
    window.addEventListener("suggestion-click", handler);
    return () => window.removeEventListener("suggestion-click", handler);
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="flex-shrink-0 px-4 md:px-8 pb-5 pt-2 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent">
      <div className="max-w-4xl mx-auto">
        <div
          className={clsx(
            "flex items-end gap-2.5 rounded-2xl p-2.5 pl-4 backdrop-blur-xl transition-all duration-200",
            "bg-slate-900/90 border shadow-2xl shadow-slate-950/80",
            disabled
              ? "border-slate-800/60 opacity-70"
              : "border-slate-700/80 focus-within:border-brand-500/80 focus-within:ring-2 focus-within:ring-brand-500/20"
          )}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={1}
            placeholder={
              disabled
                ? "Synthesizing answer from retrieved sources..."
                : "Ask any question about company policies, specs, or docs..."
            }
            aria-label="Question input"
            className={clsx(
              "flex-1 bg-transparent resize-none outline-none",
              "text-sm text-slate-100 placeholder-slate-500",
              "min-h-[28px] max-h-[200px] py-1.5",
              "scrollbar-thin scrollbar-thumb-slate-700"
            )}
            style={{ overflowY: "auto" }}
          />

          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            className={clsx(
              "flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200 cursor-pointer",
              canSend
                ? "bg-gradient-to-tr from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white shadow-lg shadow-brand-500/30 scale-100"
                : "bg-slate-800 text-slate-600 cursor-not-allowed scale-95"
            )}
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>

        <div className="flex items-center justify-between px-2 mt-2 text-[11px] text-slate-500">
          <span>Enterprise RAG · Row-Level Security Enforced</span>
          <div className="flex items-center gap-1">
            <span>Send</span>
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-[9px] font-mono text-slate-400">
              Enter ↵
            </kbd>
          </div>
        </div>
      </div>
    </div>
  );
}
