"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import type { SSEEvent } from "./api";

export function useDebateStream(debateId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!debateId) return;
    // 断开旧连接
    if (esRef.current) { esRef.current.close(); esRef.current = null; }

    const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/debates/${debateId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.addEventListener("round_start", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "round_start", ...data }]);
    });
    es.addEventListener("agent_start", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "agent_start", ...data }]);
    });
    es.addEventListener("chunk", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "chunk", ...data }]);
    });
    es.addEventListener("agent_end", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "agent_end", ...data }]);
    });
    es.addEventListener("round_end", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "round_end", ...data }]);
    });
    es.addEventListener("done", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type: "done", ...data }]);
      setDone(true);
      es.close();
    });
    es.addEventListener("error", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setEvents((prev) => [...prev, { type: "error", ...data }]);
      } catch {
        // 连接错误（断线等），EventSource 会自动重连
      }
    });

    es.onerror = () => {
      setConnected(false);
      // EventSource 自动重连，不需要手动处理
    };
  }, [debateId]);

  const disconnect = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setConnected(false);
  }, []);

  useEffect(() => {
    return () => { disconnect(); };
  }, [disconnect]);

  return { events, connected, done, connect, disconnect };
}
