/**
 * app/api/query/route.ts
 *
 * Next.js App Router API route that proxies POST /query to the FastAPI backend
 * and forwards the SSE (Server-Sent Events) stream back to the browser client.
 * This avoids CORS issues and keeps the backend URL private from the browser.
 * The Authorization header from the incoming request is forwarded as-is.
 */

import { type NextRequest } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://backend:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<Response> {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return new Response(
      JSON.stringify({ error: "Missing Authorization header" }),
      { status: 401, headers: { "Content-Type": "application/json" } }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: authHeader,
      },
      body: JSON.stringify(body),
      // @ts-expect-error — Node.js fetch duplex option
      duplex: "half",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    return new Response(
      `data: {"error":"Backend unreachable: ${msg}","done":true}\n\n`,
      {
        status: 503,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
      }
    );
  }

  if (!backendRes.ok || !backendRes.body) {
    const errText = await backendRes.text().catch(() => backendRes.statusText);
    return new Response(
      `data: {"error":"${errText}","done":true}\n\n`,
      {
        status: backendRes.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
      }
    );
  }

  // Pipe the backend SSE stream directly to the client
  return new Response(backendRes.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no", // Disable nginx buffering
    },
  });
}
