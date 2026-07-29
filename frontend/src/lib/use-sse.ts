"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import type { SSEEvent } from "./api";

export function useDebateStream(debateId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const connect = useCallback(() => {
    if (!debateId) return;
    if (abortRef.current) abortRef.current.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/debates/${debateId}/stream`;

    setConnected(false);
    setDone(false);
    setEvents([]);

    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok || !res.body) return;
        setConnected(true);
        const reader = res.body.getReader();
        readerRef.current = reader;
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEventType = "";

        while (true) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                const event: SSEEvent = { type: currentEventType || data.type, ...data };
                setEvents((prev) => [...prev, event]);
                if (event.type === "done") setDone(true);
              } catch {
                // skip malformed data
              }
            }
          }
        }
      })
      .catch(() => {
        // aborted or network error — silently handled
      });
  }, [debateId]);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    readerRef.current?.cancel();
    setConnected(false);
  }, []);

  useEffect(() => {
    return () => { disconnect(); };
  }, [disconnect]);

  return { events, connected, done, connect, disconnect };
}
