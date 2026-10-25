/**
 * lib/api.ts
 *
 * Typed API client for the RAG Knowledge Assistant backend.
 * All requests include the JWT Authorization header.
 * queryStream uses the Fetch ReadableStream API to parse SSE events
 * incrementally, calling callbacks for each token, the final done event,
 * and any error. This keeps streaming logic out of React components.
 */

import type { Document, Source } from "./types";

export function getApiBase(): string {
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

/**
 * Fetch the list of documents accessible to the authenticated user.
 * The backend filters by access_group derived from the JWT claims.
 */
export async function getDocuments(jwt?: string): Promise<Document[]> {
  const token = jwt || "dev-token";
  const res = await fetch(`${getApiBase()}/documents`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `GET /documents failed: ${res.status} ${res.statusText} — ${body}`
    );
  }

  const data = (await res.json()) as { documents: Document[] } | Document[];
  if (Array.isArray(data)) return data;
  return data.documents;
}

/**
 * Upload and index a document directly from the frontend.
 */
export async function uploadDocument(
  file: File,
  accessGroup: string,
  jwt?: string
): Promise<{ status: string; file_name: string; chunks_created: number }> {
  const token = jwt || "dev-token";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("access_group", accessGroup);

  const res = await fetch(`${getApiBase()}/documents/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(`Upload failed (${res.status}): ${errorText}`);
  }

  return (await res.json()) as { status: string; file_name: string; chunks_created: number };
}

// ---------------------------------------------------------------------------
// Streaming query
// ---------------------------------------------------------------------------

/**
 * Send a question to the backend and stream the SSE response.
 */
export async function queryStream(
  question: string,
  jwt: string,
  onToken: (token: string) => void,
  onDone: (sources: Source[], confidence: number) => void,
  onError: (errorMessage: string) => void
): Promise<void> {
  const token = jwt || "dev-token";
  let res: Response;

  try {
    res = await fetch(`${getApiBase()}/query`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ question }),
    });
  } catch (err) {
    onError(
      err instanceof Error
        ? `Network error: ${err.message}`
        : "Network error: could not reach backend"
    );
    return;
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    onError(`Backend error ${res.status}: ${body || res.statusText}`);
    return;
  }

  if (!res.body) {
    onError("Backend returned no response body");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      if (!rawEvent.trim()) continue;

      const dataLine = rawEvent
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;

      const jsonStr = dataLine.slice("data:".length).trim();
      if (!jsonStr) continue;

      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(jsonStr) as Record<string, unknown>;
      } catch {
        continue;
      }

      if ("error" in parsed && parsed.done === true) {
        onError(String(parsed.error));
        reader.cancel().catch(() => undefined);
        return;
      }

      if (parsed.done === true) {
        onDone(
          (parsed.sources as Source[]) ?? [],
          typeof parsed.confidence === "number" ? parsed.confidence : 0
        );
        reader.cancel().catch(() => undefined);
        return;
      }

      if (typeof parsed.token === "string") {
        onToken(parsed.token);
      }
    }
  }

  onDone([], 0);
}
