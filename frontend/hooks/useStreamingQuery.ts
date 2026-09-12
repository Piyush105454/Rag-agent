/**
 * hooks/useStreamingQuery.ts
 *
 * Core chat hook for the RAG Knowledge Assistant.
 * Manages the full conversation message array and orchestrates SSE streaming
 * via the queryStream API client. Each call to sendQuery:
 *   1. Appends a user message immediately
 *   2. Appends an empty assistant message with isStreaming=true
 *   3. Streams tokens into the assistant message content
 *   4. On stream done: attaches sources + confidence, clears isStreaming
 *   5. On error: attaches error string to the assistant message
 */

"use client";

import { useState, useCallback, useRef } from "react";
import { queryStream } from "@/lib/api";
import type { Message, Source } from "@/lib/types";

export interface StreamingQueryState {
  messages: Message[];
  isStreaming: boolean;
  sendQuery: (question: string, jwt: string) => Promise<void>;
  clearMessages: () => void;
}

/** Generate a simple unique ID without external deps */
function uid(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

/**
 * useStreamingQuery — manages chat message state with SSE streaming.
 */
export function useStreamingQuery(): StreamingQueryState {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  // Track the ID of the currently-streaming assistant message
  const streamingMsgId = useRef<string | null>(null);

  const sendQuery = useCallback(
    async (question: string, jwt: string): Promise<void> => {
      if (isStreaming) return; // Prevent concurrent queries

      // 1. Add user message
      const userMsg: Message = {
        id: uid(),
        role: "user",
        content: question,
      };

      // 2. Add empty assistant placeholder
      const assistantMsgId = uid();
      const assistantMsg: Message = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      streamingMsgId.current = assistantMsgId;
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      // Helper: update the assistant message by ID
      const updateAssistant = (updater: (msg: Message) => Message) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? updater(m) : m))
        );
      };

      // 3. Token callback — append each token to content
      const onToken = (token: string) => {
        updateAssistant((m) => ({ ...m, content: m.content + token }));
      };

      // 4. Done callback — attach sources + confidence, mark done
      const onDone = (sources: Source[], confidence: number) => {
        updateAssistant((m) => ({
          ...m,
          sources,
          confidence,
          isStreaming: false,
        }));
        setIsStreaming(false);
        streamingMsgId.current = null;
      };

      // 5. Error callback — attach error message
      const onError = (errorMessage: string) => {
        updateAssistant((m) => ({
          ...m,
          content: m.content, // keep any partial content
          error: errorMessage,
          isStreaming: false,
        }));
        setIsStreaming(false);
        streamingMsgId.current = null;
      };

      await queryStream(question, jwt, onToken, onDone, onError);
    },
    [isStreaming]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsStreaming(false);
    streamingMsgId.current = null;
  }, []);

  return { messages, isStreaming, sendQuery, clearMessages };
}
