/**
 * components/InputBar.tsx
 *
 * Auto-resizing textarea input bar for submitting queries.
 * - Submit on Enter (Shift+Enter inserts newline)
 * - Send button disabled while streaming is in progress
 * - Textarea auto-resizes up to a max height then scrolls
 * - Listens for `suggestion-click` custom events from ChatWindow empty state
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
import { Send } from "lucide-react";

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
    // Reset height
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
    <div className="border-t border-slate-700/50 bg-slate-900/80 backdrop-blur-sm px-4 py-3">
      <div className="max-w-4xl mx-auto">
        <div
          className={clsx(
            "flex items-end gap-2 rounded-2xl border px-4 py-2",
            "bg-slate-800 transition-colors duration-150",
            disabled
              ? "border-slate-700/40 opacity-70"
              : "border-slate-600/60 focus-within:border-brand-500/70"
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
              disabled ? "Waiting for response..." : "Ask a question..."
            }
            aria-label="Question input"
            className={clsx(
              "flex-1 bg-transparent resize-none outline-none",
              "text-sm text-slate-100 placeholder-slate-500",
              "min-h-[24px] max-h-[200px] py-1",
              "scrollbar-thin scrollbar-thumb-slate-600"
            )}
            style={{ overflowY: "auto" }}
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            className={clsx(
              "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
              "transition-all duration-150 mb-0.5",
              canSend
                ? "bg-brand-600 hover:bg-brand-500 text-white shadow-sm"
                : "bg-slate-700 text-slate-500 cursor-not-allowed"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-center text-slate-600 text-xs mt-1.5">
          Press Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
