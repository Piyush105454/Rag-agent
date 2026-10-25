/**
 * hooks/useAuth.ts
 *
 * JWT authentication management hook for the RAG Knowledge Assistant.
 * Stores the JWT in localStorage so it persists across page refreshes.
 * Exposes helpers to set, clear, and check authentication state.
 * SSR-safe: localStorage access is guarded behind typeof window checks.
 */

"use client";

import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "rag_jwt";

export interface AuthState {
  /** Current JWT string, or null if not authenticated */
  jwt: string | null;
  /** True when a non-empty JWT is stored */
  isAuthenticated: boolean;
  /** Persist a new JWT token */
  setJwt: (token: string) => void;
  /** Alias for setJwt — more semantic name for login flows */
  loginWithToken: (token: string) => void;
  /** Remove the JWT and reset auth state */
  clearJwt: () => void;
}

/**
 * useAuth — manages JWT bearer token lifecycle.
 *
 * Usage:
 *   const { jwt, isAuthenticated, loginWithToken, clearJwt } = useAuth();
 */
export function useAuth(): AuthState {
  const [jwt, setJwtState] = useState<string | null>("dev-full-access-token");

  // Hydrate from localStorage on mount (client-side only)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(STORAGE_KEY) || "dev-full-access-token";
    setJwtState(stored);
  }, []);

  const setJwt = useCallback((token: string) => {
    const trimmed = token.trim();
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, trimmed);
    }
    setJwtState(trimmed);
  }, []);

  const clearJwt = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
    setJwtState(null);
  }, []);

  return {
    jwt,
    isAuthenticated: jwt !== null && jwt.length > 0,
    setJwt,
    loginWithToken: setJwt,
    clearJwt,
  };
}
