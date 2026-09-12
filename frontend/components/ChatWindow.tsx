/**
 * components/ChatWindow.tsx
 *
 * Scrollable message list component for the RAG Knowledge Assistant chat UI.
 * Auto-scrolls to the bottom whenever a new message is added or streaming
 * content updates (via a MutationObserver on the scroll container).
 * Shows a branded empty state when no messages exist yet.
 */

"use client";

import React, { useRef, useEffect } from "react";
import type { Message } from "@/lib/types";
import MessageBubble from "./MessageBubble";

interface ChatWindowProps {
  messages: Message[];
}

export default function ChatWindow({ messages }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change or content grows during streaming
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // MutationObserver to scroll during token streaming (content changes
  // without new array entries)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new MutationObserver(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    });

    observer.observe(container, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => observer.disconnect();
  }, []);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
        <div className="w-16 h-16 rounded-2xl bg-brand-900/40 border border-brand-700/30 flex items-center justify-center mb-4">
          <svg
            className="w-8 h-8 text-brand-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-slate-200 mb-2">
          Ask anything about your company docs
        </h2>
        <p className="text-slate-400 text-sm max-w-md">
          I can search through all documents you have access to and provide
          cited answers with confidence scores.
        </p>
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
          {[
            "What is our return policy?",
            "Summarize the engineering onboarding process",
            "What are the Q3 sales targets?",
            "How do I request time off?",
          ].map((suggestion) => (
            <button
              key={suggestion}
              className="text-left px-3 py-2.5 rounded-xl border border-slate-700/60 bg-slate-800/40 hover:bg-slate-800/80 text-slate-400 hover:text-slate-200 text-xs transition-colors duration-150"
              onClick={() => {
                // Dispatch a custom event that the parent page can listen to
                window.dispatchEvent(
                  new CustomEvent("suggestion-click", { detail: suggestion })
                );
              }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto py-6 space-y-1 scroll-smooth"
      aria-live="polite"
      aria-label="Chat messages"
    >
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} className="h-1" aria-hidden="true" />
    </div>
  );
}
