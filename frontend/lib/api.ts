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

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

/**
 * Fetch the list of documents accessible to the authenticated user.
 * The backend filters by access_group derived from the JWT claims.
 */
export async function getDocuments(jwt: string): Promise<Document[]> {
  const res = await fetch(`${API_BASE}/documents`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${jwt}`,
      "Content-Type": "application/json",
    },
    // Next.js cache: do not cache document list so sidebar stays fresh
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `GET /documents failed: ${res.status} ${res.statusText} — ${body}`
    );
  }

  const data = (await res.json()) as { documents: Document[] } | Document[];
  // Handle both {documents: [...]} and bare array shapes
  if (Array.isArray(data)) return data;
  return data.documents;
}

// ---------------------------------------------------------------------------
// Streaming query
// ---------------------------------------------------------------------------

/**
 * Send a question to the backend and stream the SSE response.
 *
 * @param question  - The user's natural language question
 * @param jwt       - JWT bearer token
 * @param onToken   - Called for each incremental text token
 * @param onDone    - Called once with final sources + confidence when stream ends
 * @param onError   - Called if the backend sends an error event or fetch fails
 */
export async function queryStream(
  question: string,
  jwt: string,
  onToken: (token: string) => void,
  onDone: (sources: Source[], confidence: number) => void,
  onError: (errorMessage: string) => void
): Promise<void> {
  let res: Response;

  try {
    res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
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

  // Parse the SSE stream line by line
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newline
    const events = buffer.split("\n\n");
    // Keep any incomplete trailing chunk in the buffer
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      if (!rawEvent.trim()) continue;

      // Extract the data line(s) — SSE format: "data: <json>"
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
        // Skip malformed events
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

  // If stream ended without a done event, signal completion with no sources
  onDone([], 0);
}
