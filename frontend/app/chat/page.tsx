/**
 * app/chat/page.tsx
 *
 * Modern Enterprise AI Knowledge Assistant Interface.
 * Features:
 *   - Glassmorphic Obsidian Dark Theme with ambient glowing gradients
 *   - Direct Document Upload with drag-and-drop & live indexing progress
 *   - Document library search, filtering by access group, and format badges
 *   - Quick prompt starter cards
 *   - Auto-authenticated dev state with instant token indicator
 */

"use client";

import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
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
  Search,
  Sparkles,
  ShieldCheck,
  Cpu,
  Layers,
  FileCode,
  FileSpreadsheet,
  SlidersHorizontal,
} from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { useStreamingQuery } from "@/hooks/useStreamingQuery";
import { getDocuments, uploadDocument } from "@/lib/api";
import type { Document } from "@/lib/types";

import ChatWindow from "@/components/ChatWindow";
import InputBar from "@/components/InputBar";

// ---------------------------------------------------------------------------
// Document Sidebar Card with format-specific icons
// ---------------------------------------------------------------------------

function DocumentCard({ doc }: { doc: Document }) {
  const date = new Date(doc.indexed_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

  const ext = doc.file_name.split(".").pop()?.toLowerCase();

  const Icon = useMemo(() => {
    if (ext === "pdf") return FileText;
    if (ext === "pptx" || ext === "ppt") return Layers;
    if (ext === "xlsx" || ext === "csv") return FileSpreadsheet;
    return FileCode;
  }, [ext]);

  return (
    <div className="group relative px-3 py-2.5 rounded-xl border border-slate-800/60 bg-slate-900/50 hover:bg-slate-800/80 hover:border-slate-700/80 transition-all duration-150 cursor-pointer shadow-sm hover:shadow-md">
      <div className="flex items-start gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:border-brand-500/50 group-hover:bg-brand-950/30 transition-colors">
          <Icon className="w-3.5 h-3.5 text-brand-400 group-hover:text-brand-300 transition-colors" />
        </div>
        <div className="flex-1 min-w-0">
          <p
            className="text-xs text-slate-200 font-medium truncate leading-tight group-hover:text-white transition-colors"
            title={doc.file_name}
          >
            {doc.file_name}
          </p>
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[9px] font-semibold bg-brand-950/80 text-brand-300 border border-brand-800/40 uppercase tracking-wider">
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
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setSuccessMsg(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
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
      }, 1600);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-md bg-slate-900/95 border border-slate-800 rounded-2xl shadow-2xl shadow-brand-950/40 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Upload Knowledge Source</h2>
              <p className="text-[10px] text-slate-400">Add documents to your vector index</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1.5 rounded-lg hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleUpload} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-950/40 border border-red-700/50 rounded-xl text-xs text-red-300 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-emerald-950/40 border border-emerald-700/50 rounded-xl text-xs text-emerald-300 flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Drag & drop zone */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Document File
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                "border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200",
                isDragging
                  ? "border-brand-400 bg-brand-950/30 scale-[1.01]"
                  : file
                  ? "border-brand-500/60 bg-brand-950/20"
                  : "border-slate-700/80 hover:border-slate-500 bg-slate-950/40 hover:bg-slate-800/40"
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
              <div className="w-10 h-10 rounded-xl bg-slate-800/80 border border-slate-700/60 mx-auto flex items-center justify-center mb-2.5 text-brand-400">
                <FileText className="w-5 h-5" />
              </div>
              {file ? (
                <div>
                  <p className="text-xs font-semibold text-slate-200 truncate">{file.name}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB · Ready to parse
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-medium text-slate-200">
                    Click to browse or drop file here
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Supports PDF, PPTX, TXT, MD up to 200MB
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Access Control Group */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Access Permission Group
            </label>
            <div className="relative">
              <select
                value={accessGroup}
                onChange={(e) => setAccessGroup(e.target.value)}
                disabled={isUploading}
                className="w-full text-xs bg-slate-950/60 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-slate-200 outline-none focus:border-brand-500 transition-colors appearance-none cursor-pointer"
              >
                <option value="general">general (Accessible to all company members)</option>
                <option value="engineering">engineering (Engineering docs & specs)</option>
                <option value="sales">sales (Sales policy & quotas)</option>
                <option value="product">product (PRDs & product roadmaps)</option>
              </select>
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500 absolute right-3.5 top-3 pointer-events-none" />
            </div>
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors rounded-lg hover:bg-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!file || isUploading}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 disabled:opacity-40 text-white text-xs font-semibold rounded-xl shadow-lg shadow-brand-600/30 transition-all cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Chunking & Indexing...</span>
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
// Modern Header Bar with Status Pills
// ---------------------------------------------------------------------------

function HeaderBar({
  docCount,
  jwt,
  onSetJwt,
  onClearJwt,
}: {
  docCount: number;
  jwt: string | null;
  onSetJwt: (t: string) => void;
  onClearJwt: () => void;
}) {
  const [showInput, setShowInput] = useState(false);
  const [inputVal, setInputVal] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputVal.trim()) {
      onSetJwt(inputVal.trim());
      setInputVal("");
      setShowInput(false);
    }
  };

  return (
    <header className="flex-shrink-0 flex items-center justify-between px-6 py-3.5 bg-slate-900/60 backdrop-blur-md border-b border-slate-800/80 z-10">
      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-slate-100 tracking-tight">
              Enterprise Knowledge Assistant
            </h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
              Live
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Groq LPU Acceleration · pgvector HNSW · {docCount} sources indexed
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Model tags */}
        <div className="hidden md:flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/50 border border-slate-700/40 text-[10px] text-slate-300">
            <Cpu className="w-3 h-3 text-brand-400" />
            <span>openai/gpt-oss-120b</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/50 border border-slate-700/40 text-[10px] text-slate-300">
            <ShieldCheck className="w-3 h-3 text-indigo-400" />
            <span>RBAC Protected</span>
          </div>
        </div>

        {/* Auth pill */}
        {showInput ? (
          <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Paste JWT token..."
              className="text-xs bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-200 outline-none focus:border-brand-500 font-mono w-48"
              autoFocus
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition-colors"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setShowInput(false)}
              className="p-1.5 text-slate-400 hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <div
            onClick={() => setShowInput(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 cursor-pointer transition-colors"
            title="Click to view/change JWT token"
          >
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-xs text-slate-300 font-medium">Full Access</span>
            <ChevronRight className="w-3 h-3 text-slate-500" />
          </div>
        )}
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Main Chat Page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const { jwt, isAuthenticated, loginWithToken, clearJwt } = useAuth();
  const { messages, isStreaming, sendQuery, clearMessages } = useStreamingQuery();

  const [documents, setDocuments] = useState<Document[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<string>("all");

  // Fetch documents
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

  // Filtered documents by search query and access group
  const filteredDocs = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch = doc.file_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesGroup = selectedGroup === "all" || doc.access_group === selectedGroup;
      return matchesSearch && matchesGroup;
    });
  }, [documents, searchQuery, selectedGroup]);

  // Query submission handler
  const handleSend = useCallback(
    (question: string) => {
      void sendQuery(question, jwt || "dev-token");
    },
    [jwt, sendQuery]
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/20 text-slate-100">
      {/* ------------------------------------------------------------------ */}
      {/* LEFT SIDEBAR                                                         */}
      {/* ------------------------------------------------------------------ */}
      <aside className="w-72 flex-shrink-0 flex flex-col bg-slate-950/70 backdrop-blur-xl border-r border-slate-800/80">
        {/* Brand / Logo */}
        <div className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand-500/20">
              <Database className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">RAG Assistant</p>
              <p className="text-[10px] text-slate-400">Enterprise Knowledge Hub</p>
            </div>
          </div>
        </div>

        {/* Upload Button */}
        <div className="p-3 border-b border-slate-800/60">
          <button
            onClick={() => setIsUploadOpen(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand-600 via-indigo-600 to-brand-600 hover:from-brand-500 hover:to-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-brand-600/25 transition-all duration-200 cursor-pointer active:scale-[0.98]"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>+ Upload Document</span>
          </button>
        </div>

        {/* Search & Filter Header */}
        <div className="px-3 pt-3 pb-2 space-y-2 border-b border-slate-800/40">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              className="w-full bg-slate-900/80 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 outline-none focus:border-brand-500/70 transition-colors"
            />
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none text-[10px]">
            {["all", "general", "engineering", "sales", "product"].map((grp) => (
              <button
                key={grp}
                onClick={() => setSelectedGroup(grp)}
                className={clsx(
                  "px-2 py-0.5 rounded-md font-medium capitalize transition-colors flex-shrink-0",
                  selectedGroup === grp
                    ? "bg-brand-600 text-white"
                    : "bg-slate-800/40 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                )}
              >
                {grp}
              </button>
            ))}
          </div>
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto py-2 px-2.5 space-y-1">
          <div className="flex items-center justify-between px-1 mb-1">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              {filteredDocs.length} {filteredDocs.length === 1 ? "Source" : "Sources"}
            </span>
            <button
              onClick={() => void fetchDocs()}
              disabled={docsLoading}
              className="p-1 rounded-md hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
              title="Refresh sources"
            >
              <RefreshCw className={clsx("w-3 h-3", docsLoading && "animate-spin")} />
            </button>
          </div>

          {/* Loading Skeleton */}
          {docsLoading && (
            <div className="space-y-2 px-1 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse bg-slate-900/60 rounded-xl p-3 border border-slate-800/40">
                  <div className="h-3 bg-slate-800 rounded w-3/4 mb-2" />
                  <div className="h-2 bg-slate-800/60 rounded w-1/2" />
                </div>
              ))}
            </div>
          )}

          {/* Document Cards */}
          {!docsLoading && filteredDocs.length > 0 && (
            <div className="space-y-1.5">
              {filteredDocs.map((doc) => (
                <DocumentCard key={`${doc.file_name}-${doc.access_group}`} doc={doc} />
              ))}
            </div>
          )}

          {/* Empty State */}
          {!docsLoading && filteredDocs.length === 0 && (
            <div className="px-3 py-8 text-center">
              <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto mb-2.5 text-slate-600">
                <BookOpen className="w-5 h-5" />
              </div>
              <p className="text-xs text-slate-300 font-medium">No documents found</p>
              <p className="text-[10px] text-slate-500 mt-1 max-w-[180px] mx-auto">
                {searchQuery
                  ? "Try adjusting your search filter"
                  : "Click '+ Upload Document' above to index your first file."}
              </p>
            </div>
          )}
        </div>

        {/* Clear chat bottom bar */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-950/40">
          <button
            onClick={clearMessages}
            disabled={messages.length === 0}
            className="w-full text-xs text-slate-400 hover:text-slate-200 disabled:opacity-30 transition-colors py-2 rounded-xl hover:bg-slate-800/60 border border-slate-800 text-center font-medium"
          >
            Clear conversation
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* MAIN CHAT AREA                                                       */}
      {/* ------------------------------------------------------------------ */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Top Header */}
        <HeaderBar
          docCount={documents.length}
          jwt={jwt}
          onSetJwt={loginWithToken}
          onClearJwt={clearJwt}
        />

        {/* Chat Window */}
        <ChatWindow messages={messages} />

        {/* Pinned Input Bar */}
        <InputBar onSend={handleSend} disabled={isStreaming} />
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
