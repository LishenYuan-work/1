"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiBase, authToken, type ReviewEvent } from "./api";

export type { ReviewEvent } from "./api";

export function useReviewStream(sessionId: string | null, onEvent: (event: ReviewEvent) => void, guest = false) {
  const [connected, setConnected] = useState(false);
  const last = useRef(0);
  const activeSession = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const connect = useCallback(async (targetSessionId = sessionId) => {
    if (!targetSessionId) return;
    if (activeSession.current !== targetSessionId) { last.current = 0; activeSession.current = targetSessionId; }
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    let attempt = 0;
    try {
      while (!controller.signal.aborted && attempt < 6) {
        try {
          const token = authToken();
          const headers: Record<string, string> = { "Last-Event-ID": String(last.current) };
          if (token) headers.Authorization = `Bearer ${token}`;
          const prefix = guest ? "/api/guest/reviews" : "/api/reviews";
          const response = await fetch(`${apiBase()}${prefix}/${targetSessionId}/stream`, {
            headers,
            credentials: "include", signal: controller.signal,
          });
          if (!response.ok || !response.body) throw new Error("SSE connection failed");
          setConnected(true); attempt = 0;
          const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let finished = false;
          while (!controller.signal.aborted) {
            const { value, done } = await reader.read(); if (done) break;
            buffer += decoder.decode(value, { stream: true }); const chunks = buffer.split("\n\n"); buffer = chunks.pop() || "";
            for (const chunk of chunks) {
              const dataLine = chunk.split("\n").find((line) => line.startsWith("data: ")); if (!dataLine) continue;
              const event = JSON.parse(dataLine.slice(6)) as ReviewEvent;
              if (event.sequence && event.sequence <= last.current) continue;
              last.current = event.sequence || last.current; onEvent(event);
              if (event.type === "done") { finished = true; break; }
            }
            if (finished) return;
          }
        } catch { if (controller.signal.aborted) return; }
        setConnected(false); attempt += 1;
        if (attempt < 6) await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * 2 ** (attempt - 1), 10000)));
      }
    } finally { if (!controller.signal.aborted) setConnected(false); }
  }, [sessionId, onEvent, guest]);

  useEffect(() => () => abort.current?.abort(), [sessionId, guest]);
  return { connect, connected };
}
