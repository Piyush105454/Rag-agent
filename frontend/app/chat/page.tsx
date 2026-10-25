/**
 * app/chat/page.tsx
 *
 * Main chat interface for the RAG Knowledge Assistant.
 * Includes direct frontend document upload (PDF, PPTX, TXT, MD) with live indexing,
 * auto-authenticated developer state, and interactive citation sidebar.
 */

"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import clsx from "clsx";
import {
  BookOpen,
  RefreshCw,
  LogOut,
  ChevronRight,
  AlertCircle,
  Database,
  Upload,
  X,
  FileText,
  CheckCircle2,
  Loader2,
} from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { useStreamingQuery } from "@/hooks/useStreamingQuery";
import { getDocuments, uploadDocument } from "@/lib/api";
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
// Upload Document Modal
// ---------------------------------------------------------------------------

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  jwt: string | null;
}

function UploadModal({ isOpen, onClose, onSuccess, jwt }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [accessGroup, setAccessGroup] = useState<string>("general");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setSuccessMsg(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }

    setIsUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await uploadDocument(file, accessGroup, jwt || undefined);
      setSuccessMsg(`Successfully indexed ${res.file_name} (${res.chunks_created} chunks)!`);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      onSuccess();
      setTimeout(() => {
        onClose();
        setSuccessMsg(null);
      }, 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-brand-400" />
            <h2 className="text-sm font-semibold text-slate-100">Upload to Knowledge Base</h2>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleUpload} className="p-5 space-y-4">
          {error && (
            <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-xs text-red-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-emerald-900/30 border border-emerald-700/50 rounded-lg text-xs text-emerald-300 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* File input / dropzone */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Select Document (PDF, PPTX, TXT, MD)
            </label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                "border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors",
                file
                  ? "border-brand-500 bg-brand-950/20"
                  : "border-slate-700 hover:border-slate-500 bg-slate-800/40"
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.pptx,.ppt,.txt,.md"
                onChange={handleFileChange}
                className="hidden"
                disabled={isUploading}
              />
              <FileText className="w-8 h-8 text-brand-400 mx-auto mb-2 opacity-80" />
              {file ? (
                <div>
                  <p className="text-xs font-medium text-slate-200 truncate">{file.name}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-medium text-slate-300">
                    Click to select file from your computer
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">Supports PDF, PPTX, TXT, MD</p>
                </div>
              )}
            </div>
          </div>

          {/* Access Group Dropdown */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Access Control Group
            </label>
            <select
              value={accessGroup}
              onChange={(e) => setAccessGroup(e.target.value)}
              disabled={isUploading}
              className="w-full text-xs bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 outline-none focus:border-brand-500"
            >
              <option value="general">general (All employees)</option>
              <option value="engineering">engineering (Engineering docs)</option>
              <option value="sales">sales (Sales policies & quotas)</option>
              <option value="product">product (Roadmaps & PRDs)</option>
            </select>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!file || isUploading}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:hover:bg-brand-600 text-white text-xs font-medium rounded-lg shadow-lg shadow-brand-600/20 transition-all"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Parsing & Indexing...</span>
                </>
              ) : (
                <>
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload & Index</span>
                </>
              )}
            </button>
          </div>
        </form>
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
  const [expanded, setExpanded] = useState(false);

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
        title="Click to view/change JWT token"
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
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Fetch documents whenever JWT changes
  const fetchDocs = useCallback(async () => {
    setDocsLoading(true);
    setDocsError(null);
    try {
      const docs = await getDocuments(jwt || undefined);
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
      void sendQuery(question, jwt || "dev-token");
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

        {/* Upload Button */}
        <div className="p-3 border-b border-slate-800">
          <button
            onClick={() => setIsUploadOpen(true)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-brand-600/20 transition-all"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Document</span>
          </button>
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
              disabled={docsLoading}
              className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
              title="Refresh document list"
            >
              <RefreshCw
                className={clsx("w-3 h-3", docsLoading && "animate-spin")}
              />
            </button>
          </div>

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
          {!docsLoading && documents.length === 0 && !docsError && (
            <div className="px-2 py-6 text-center">
              <BookOpen className="w-6 h-6 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400 font-medium">No documents yet</p>
              <p className="text-[10px] text-slate-500 mt-1">
                Click "+ Upload Document" above to index your first PDF or PPTX file.
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

        {/* Chat window */}
        <ChatWindow messages={messages} />

        {/* Input bar */}
        <InputBar
          onSend={handleSend}
          disabled={isStreaming}
        />
      </main>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => void fetchDocs()}
        jwt={jwt}
      />
    </div>
  );
}
