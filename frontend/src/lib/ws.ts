import { useEffect, useRef, useState } from "react";
import { api } from "./api";

export type WsConnectionStatus = "CONNECTED" | "RECONNECTING" | "DISCONNECTED";

type Listener = (msg: any) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private statusListeners: Set<(s: WsConnectionStatus) => void> = new Set();
  private status: WsConnectionStatus = "DISCONNECTED";
  private reconnectTimer: number | null = null;
  private retryDelay = 1000;
  private isExplicitlyClosed = false;

  public getStatus(): WsConnectionStatus {
    return this.status;
  }

  private setStatus(newStatus: WsConnectionStatus) {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((cb) => cb(newStatus));
    }
  }

  public connect() {
    const token = api.getToken();
    if (!token) {
      this.setStatus("DISCONNECTED");
      return;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.setStatus("RECONNECTING");

    try {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const wsUrl = `${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.setStatus("CONNECTED");
        this.retryDelay = 1000;
      };

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.listeners.forEach((listener) => {
            try {
              listener(parsed);
            } catch (err) {
              console.error("Error in WS event listener:", err);
            }
          });
        } catch {
          // ignore malformed frame
        }
      };

      this.ws.onerror = () => {
        // Handled in onclose
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (!this.isExplicitlyClosed) {
          this.setStatus("RECONNECTING");
          this.scheduleReconnect();
        } else {
          this.setStatus("DISCONNECTED");
        }
      };
    } catch {
      this.setStatus("DISCONNECTED");
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
    }
    const jitter = Math.random() * 500;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.retryDelay + jitter);

    this.retryDelay = Math.min(this.retryDelay * 1.5, 10000);
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.setStatus("DISCONNECTED");
  }

  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
      this.connect();
    }
    return () => {
      this.listeners.delete(listener);
    };
  }

  public subscribeStatus(listener: (s: WsConnectionStatus) => void): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => {
      this.statusListeners.delete(listener);
    };
  }
}

const manager = new WebSocketManager();

/**
 * Subscribes to live emergency events.
 * Event carries event_type and identifiers; handlers should re-fetch via REST for the full payload.
 */
export function useEmergencyEvents(onEvent: (msg: any) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    const unsub = manager.subscribe((data) => {
      cb.current(data);
    });
    return unsub;
  }, []);
}

/**
 * Returns the current WebSocket connection state: "CONNECTED" | "RECONNECTING" | "DISCONNECTED"
 */
export function useWsConnectionStatus(): WsConnectionStatus {
  const [status, setStatus] = useState<WsConnectionStatus>(manager.getStatus());

  useEffect(() => {
    return manager.subscribeStatus(setStatus);
  }, []);

  return status;
}
