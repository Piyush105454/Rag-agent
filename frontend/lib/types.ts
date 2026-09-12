/**
 * lib/types.ts
 *
 * Shared TypeScript types used across the RAG Knowledge Assistant frontend.
 * These types mirror the backend API response shapes exactly so that
 * end-to-end type safety is maintained without a separate codegen step.
 */

/** A single chat message in the conversation thread. */
export interface Message {
  /** Unique identifier (nanoid or crypto.randomUUID) */
  id: string;
  /** Who sent this message */
  role: "user" | "assistant";
  /** Accumulated text content (grows during streaming) */
  content: string;
  /** Source documents cited by the assistant — populated after streaming ends */
  sources?: Source[];
  /** Confidence score 0-1 — populated after streaming ends */
  confidence?: number;
  /** True while the SSE stream is still open for this message */
  isStreaming?: boolean;
  /** Non-null when the backend or network returned an error */
  error?: string;
}

/** A source document chunk cited in an assistant answer. */
export interface Source {
  /** Original filename as stored in the vector DB */
  file: string;
  /** 1-based page number within the document */
  page: number;
  /** Unique chunk identifier from the vector DB */
  chunk_id: string;
}

/** A document record returned by GET /documents */
export interface Document {
  /** Original filename */
  file_name: string;
  /** Access group this document belongs to */
  access_group: string;
  /** ISO timestamp of last index */
  indexed_at: string;
  /** Number of text chunks stored for this document */
  chunk_count: number;
  /** Source system ("drive" | "local" | etc.) */
  source: string;
}

/** Full non-streaming query response shape (used for type reference) */
export interface QueryResponse {
  answer: string;
  sources: Source[];
  confidence: number;
}

/** SSE token event payload */
export interface SSETokenEvent {
  token: string;
}

/** SSE done event payload */
export interface SSEDoneEvent {
  sources: Source[];
  confidence: number;
  done: true;
}

/** SSE error event payload */
export interface SSEErrorEvent {
  error: string;
  done: true;
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent | SSEErrorEvent;
