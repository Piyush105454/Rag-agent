/**
 * components/ChatWindow.tsx
 *
 * Scrollable message list component for the RAG Knowledge Assistant.
 * Auto-scrolls smoothly during token streaming.
 * Includes a modern, categorized empty state with 1-click starter prompts.
 */

"use client";

import React, { useRef, useEffect } from "react";
import { Sparkles, FileText, ShieldAlert, Award, Compass } from "lucide-react";
import type { Message } from "@/lib/types";
import MessageBubble from "./MessageBubble";

interface ChatWindowProps {
  messages: Message[];
}

export default function ChatWindow({ messages }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when messages array changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // MutationObserver to auto-scroll during token streaming
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
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6 py-12 overflow-y-auto">
        {/* Glowing Logo */}
        <div className="relative mb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-xl shadow-brand-500/25 ring-1 ring-white/20">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-brand-500 to-indigo-500 opacity-20 blur-lg pointer-events-none" />
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold text-white tracking-tight mb-2">
          What would you like to know today?
        </h2>
        <p className="text-slate-400 text-sm max-w-lg mb-8 leading-relaxed">
          I synthesize answers from your authorized internal company documents, policies,
          and engineering specs with verified source citations and confidence scores.
        </p>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
          {[
            {
              title: "Return & Refund Policy",
              desc: "What are the rules and timelines for customer returns?",
              icon: FileText,
            },
            {
              title: "Engineering Onboarding",
              desc: "Summarize setup steps, repository access, and tools.",
              icon: Compass,
            },
            {
              title: "Sales Commission & Quotas",
              desc: "How are quarterly incentives and targets calculated?",
              icon: Award,
            },
            {
              title: "Compliance & Security",
              desc: "What are the required data handling & NDA protocols?",
              icon: ShieldAlert,
            },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.title}
                onClick={() => {
                  window.dispatchEvent(
                    new CustomEvent("suggestion-click", { detail: item.desc })
                  );
                }}
                className="group p-4 text-left rounded-2xl border border-slate-800 bg-slate-900/60 hover:bg-slate-850 hover:border-brand-500/50 transition-all duration-200 shadow-sm hover:shadow-lg hover:shadow-brand-950/40 cursor-pointer text-left"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-brand-400 group-hover:text-brand-300 group-hover:bg-brand-950/50 transition-colors">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white transition-colors">
                    {item.title}
                  </h3>
                </div>
                <p className="text-[11px] text-slate-400 leading-snug line-clamp-2">
                  {item.desc}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto py-6 px-4 md:px-8 space-y-6 scroll-smooth"
      aria-live="polite"
      aria-label="Chat messages"
    >
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
      <div ref={bottomRef} className="h-2" aria-hidden="true" />
    </div>
  );
}
