/**
 * app/chat/page.tsx
 *
 * Main chat interface for the RAG Knowledge Assistant.
 *
 * Layout (full-height flex row):
 *   - Left sidebar (w-64): Document library listing all accessible docs
 *   - Main area: Top bar + ChatWindow (scrollable) + InputBar (pinned bottom)
 *
 * Auth: JWT stored in localStorage via useAuth hook. A dev token input field
 * in the top bar allows pasting a JWT for testing without a real login page.
 *
 * Documents: Fetched on mount and on JWT change via GET /documents.
 * Chat: Managed by useStreamingQuery which handles SSE streaming.
 */

"use client";

import React, { useEffect, useState, useCallback } from "react";
import clsx from "clsx";
import { BookOpen, RefreshCw, LogOut, ChevronRight, AlertCircle, Database } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { useStreamingQuery } from "@/hooks/useStreamingQuery";
import { getDocuments } from "@/lib/api";
import type { Document } from "@/lib/types";

import ChatWindow from "@/components/ChatWindow";
import InputBar from "@/components/InputBar";

// ---------------------------------------------------------------------------
// Document sidebar card
// ---------------------------------------------------------------------------

function DocumentCard({ doc }: { doc: Document }) {
  const date = new Date(doc.indexed_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="group px-3 py-2.5 rounded-lg hover:bg-slate-700/40 transition-colors duration-100 cursor-default">
      <div className="flex items-start gap-2">
        <BookOpen className="w-3.5 h-3.5 text-brand-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p
            className="text-xs text-slate-200 font-medium truncate leading-snug"
            title={doc.file_name}
          >
            {doc.file_name}
          </p>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-brand-900/40 text-brand-300 border border-brand-700/30">
              {doc.access_group}
            </span>
            <span className="text-[10px] text-slate-500">
              {doc.chunk_count} chunks · {date}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// JWT token input (dev helper)
// ---------------------------------------------------------------------------

interface TokenInputProps {
  currentJwt: string | null;
  onSet: (token: string) => void;
  onClear: () => void;
}

function TokenInput({ currentJwt, onSet, onClear }: TokenInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [expanded, setExpanded] = useState(!currentJwt);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) {
      onSet(trimmed);
      setInputValue("");
      setExpanded(false);
    }
  };

  if (!expanded && currentJwt) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-900/30 border border-emerald-700/40 hover:bg-emerald-900/50 transition-colors"
        title="Click to change JWT"
      >
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs text-emerald-300 font-medium">Authenticated</span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClear();
            setExpanded(true);
          }}
          className="ml-1 text-emerald-500 hover:text-red-400 transition-colors"
          title="Log out"
        >
          <LogOut className="w-3 h-3" />
        </button>
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder="Paste JWT token..."
        className="text-xs bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-slate-200 placeholder-slate-500 outline-none focus:border-brand-500 w-64 font-mono"
        autoFocus
      />
      <button
        type="submit"
        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition-colors"
      >
        <ChevronRight className="w-3 h-3" /> Set Token
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const { jwt, isAuthenticated, loginWithToken, clearJwt } = useAuth();
  const { messages, isStreaming, sendQuery, clearMessages } = useStreamingQuery();

  const [documents, setDocuments] = useState<Document[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Fetch documents whenever JWT changes
  const fetchDocs = useCallback(async () => {
    if (!jwt) {
      setDocuments([]);
      return;
    }
    setDocsLoading(true);
    setDocsError(null);
    try {
      const docs = await getDocuments(jwt);
      setDocuments(docs);
    } catch (err) {
      setDocsError(
        err instanceof Error ? err.message : "Failed to load documents"
      );
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, [jwt]);

  useEffect(() => {
    void fetchDocs();
  }, [fetchDocs]);

  // Handle query submission
  const handleSend = useCallback(
    (question: string) => {
      if (!jwt) return;
      void sendQuery(question, jwt);
    },
    [jwt, sendQuery]
  );

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* ------------------------------------------------------------------ */}
      {/* LEFT SIDEBAR                                                         */}
      {/* ------------------------------------------------------------------ */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-slate-900 border-r border-slate-800">
        {/* Logo / branding */}
        <div className="px-4 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center flex-shrink-0">
              <Database className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-100 leading-tight">
                Knowledge Base
              </p>
              <p className="text-[10px] text-slate-500">Accessible documents</p>
            </div>
          </div>
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto py-2 px-2">
          {/* Refresh + count header */}
          <div className="flex items-center justify-between px-1 mb-1">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">
              {documents.length} documents
            </span>
            <button
              onClick={() => void fetchDocs()}
              disabled={docsLoading || !isAuthenticated}
              className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
              title="Refresh document list"
            >
              <RefreshCw
                className={clsx("w-3 h-3", docsLoading && "animate-spin")}
              />
            </button>
          </div>

          {/* Not authenticated */}
          {!isAuthenticated && (
            <div className="px-2 py-4 text-center">
              <p className="text-xs text-slate-500">
                Set your JWT token to see your documents
              </p>
            </div>
          )}

          {/* Error state */}
          {docsError && (
            <div className="mx-1 my-2 p-2 rounded-lg bg-red-900/20 border border-red-700/30">
              <div className="flex items-start gap-1.5">
                <AlertCircle className="w-3 h-3 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-[10px] text-red-300 break-words">{docsError}</p>
              </div>
            </div>
          )}

          {/* Loading skeleton */}
          {docsLoading && (
            <div className="space-y-2 px-1 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-3 bg-slate-700 rounded w-3/4 mb-1.5" />
                  <div className="h-2 bg-slate-800 rounded w-1/2" />
                </div>
              ))}
            </div>
          )}

          {/* Document cards */}
          {!docsLoading && documents.length > 0 && (
            <div className="space-y-0.5">
              {documents.map((doc) => (
                <DocumentCard key={`${doc.file_name}-${doc.access_group}`} doc={doc} />
              ))}
            </div>
          )}

          {/* Empty state */}
          {!docsLoading && isAuthenticated && documents.length === 0 && !docsError && (
            <div className="px-2 py-6 text-center">
              <BookOpen className="w-6 h-6 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-500">No documents found</p>
              <p className="text-[10px] text-slate-600 mt-1">
                Your access groups may not have indexed documents yet.
              </p>
            </div>
          )}
        </div>

        {/* Bottom: clear chat */}
        <div className="px-3 py-3 border-t border-slate-800">
          <button
            onClick={clearMessages}
            disabled={messages.length === 0}
            className="w-full text-xs text-slate-500 hover:text-slate-300 disabled:opacity-30 transition-colors py-1.5 rounded-lg hover:bg-slate-800 text-center"
          >
            Clear conversation
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* MAIN AREA                                                            */}
      {/* ------------------------------------------------------------------ */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex-shrink-0 flex items-center justify-between px-6 py-3 bg-slate-900/80 backdrop-blur-sm border-b border-slate-800">
          <div>
            <h1 className="text-sm font-semibold text-slate-100">
              Company Knowledge Assistant
            </h1>
            <p className="text-[10px] text-slate-500">
              Powered by RAG · {documents.length} docs accessible
            </p>
          </div>
          <TokenInput
            currentJwt={jwt}
            onSet={loginWithToken}
            onClear={clearJwt}
          />
        </header>

        {/* No JWT warning banner */}
        {!isAuthenticated && (
          <div className="flex-shrink-0 px-6 py-2 bg-yellow-900/20 border-b border-yellow-800/30">
            <div className="flex items-center gap-2 text-xs text-yellow-300">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              <span>
                Paste your JWT token in the top-right field to start chatting.
                Generate one with:{" "}
                <code className="bg-yellow-900/40 px-1 rounded font-mono text-[10px]">
                  python scripts/generate_jwt.py --user-id alice --groups engineering
                </code>
              </span>
            </div>
          </div>
        )}

        {/* Chat window */}
        <ChatWindow messages={messages} />

        {/* Input bar */}
        <InputBar
          onSend={handleSend}
          disabled={isStreaming || !isAuthenticated}
        />
      </main>
    </div>
  );
}
