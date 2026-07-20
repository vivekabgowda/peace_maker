'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuthStore } from '@/stores/authStore';

export interface WsMessage {
  channel: string;
  event: string;
  data: unknown;
  ts: string;
}

export type ConnState = 'connecting' | 'open' | 'closed';

function resolveWsUrl(token: string): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return `${explicit}?token=${token}`;
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${window.location.host}/api/v1/ws?token=${token}`;
  }
  return '';
}

/**
 * Resilient dashboard WebSocket hook.
 *
 * Subscribes to the given channels, auto-reconnects with backoff, and invokes
 * `onMessage` for every event. Returns the live connection state and the
 * timestamp of the last message (used for the data-freshness indicator).
 */
export function useMarketSocket(channels: string[], onMessage: (msg: WsMessage) => void) {
  const token = useAuthStore((s) => s.accessToken);
  const [state, setState] = useState<ConnState>('closed');
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const closedByUs = useRef(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const channelKey = channels.join(',');

  const connect = useCallback(() => {
    if (!token) return;
    setState('connecting');
    const ws = new WebSocket(resolveWsUrl(token));
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setState('open');
      ws.send(JSON.stringify({ action: 'subscribe', channels: channelKey.split(',') }));
    };
    ws.onmessage = (ev) => {
      setLastMessageAt(Date.now());
      try {
        onMessageRef.current(JSON.parse(ev.data) as WsMessage);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      setState('closed');
      if (closedByUs.current) return;
      const delay = Math.min(15000, 500 * 2 ** attemptRef.current++);
      setTimeout(connect, delay + Math.random() * 300);
    };
    ws.onerror = () => ws.close();
  }, [token, channelKey]);

  useEffect(() => {
    closedByUs.current = false;
    connect();
    return () => {
      closedByUs.current = true;
      wsRef.current?.close();
    };
  }, [connect]);

  return { state, lastMessageAt };
}
