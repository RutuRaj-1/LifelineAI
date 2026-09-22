import { useEffect, useRef } from "react";
import { api } from "./api";

/** Live emergency events (see backend/app/ws.py). Auto-reconnects; each event only carries ids,
 * so handlers should re-fetch via REST for the full, permission-checked payload. */
export function useEmergencyEvents(onEvent: (msg: any) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    const token = api.getToken();
    if (!token) return;
    let ws: WebSocket | null = null;
    let closedByUs = false;
    let retry = 1000;

    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token!)}`);
      ws.onmessage = (e) => {
        try { cb.current(JSON.parse(e.data)); } catch { /* ignore malformed frame */ }
      };
      ws.onclose = () => {
        if (closedByUs) return;
        setTimeout(connect, retry);
        retry = Math.min(retry * 1.5, 10000);
      };
    }
    connect();
    return () => { closedByUs = true; ws?.close(); };
  }, []);
}
