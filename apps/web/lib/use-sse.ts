"use client";

import { useEffect, useState } from "react";

export function useSSE(url: string | null, accessToken: string | null) {
  const [status, setStatus] = useState<"idle" | "connecting" | "connected" | "error">("idle");

  useEffect(() => {
    if (!url || !accessToken) {
      setStatus("idle");
      return;
    }
    let active = true;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    setStatus("connecting");

    async function connect() {
      try {
        const lastEventId = sessionStorage.getItem(`sse:${url}`) ?? "0";
        const response = await fetch(url!, {
          headers: { Authorization: `Bearer ${accessToken}`, "Last-Event-ID": lastEventId },
          signal: controller.signal
        });
        if (!response.ok || !response.body) throw new Error("SSE connection failed");
        if (active) setStatus("connected");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffered = "";
        while (active) {
          const { value, done } = await reader.read();
          if (done) break;
          buffered += decoder.decode(value, { stream: true });
          const events = buffered.split("\n\n");
          buffered = events.pop() ?? "";
          for (const event of events) {
            const id = event.split("\n").find((line) => line.startsWith("id: "))?.slice(4);
            if (id) sessionStorage.setItem(`sse:${url}`, id);
          }
        }
      } catch {
        if (!active) return;
        setStatus("error");
        retry = setTimeout(connect, 2_000);
      }
    }

    void connect();
    return () => {
      active = false;
      controller.abort();
      if (retry) clearTimeout(retry);
    };
  }, [accessToken, url]);

  return status;
}
