/**
 * app/page.tsx
 *
 * Root page — immediately redirects to /chat.
 * Using Next.js permanent redirect so browsers and crawlers go directly
 * to the chat interface without an extra round-trip in production.
 */

import { redirect } from "next/navigation";

export default function RootPage(): never {
  redirect("/chat");
}
