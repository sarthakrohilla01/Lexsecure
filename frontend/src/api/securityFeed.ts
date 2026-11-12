import { WS_URL, getAuthToken } from './client';

export interface SecurityEvent {
  event: string;
  data: any;
  receivedAt: number;
}

export interface FeedState {
  connected: boolean;
  events: SecurityEvent[];
  revision: number;
}

const MAX_EVENTS = 50;

type Listener = (state: FeedState) => void;

let socket: WebSocket | null = null;
let retryTimer: number | null = null;
let pingTimer: number | null = null;
let reconnectAttempt = 0;
let revision = 0;
let authFailed = false;
const listeners = new Set<Listener>();
const state: FeedState = { connected: false, events: [], revision: 0 };

function emit() {
  const snapshot = { connected: state.connected, events: state.events, revision: state.revision };
  listeners.forEach((l) => l(snapshot));
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const token = getAuthToken();
  if (!token) return;

  authFailed = false;

  let ws: WebSocket;
  try {
    ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
  } catch {
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.onopen = () => {
    reconnectAttempt = 0;
    state.connected = true;
    emit();
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (!msg.event || msg.event === 'pong') return;
      revision += 1;
      state.revision = revision;
      state.events = [
        { event: msg.event, data: msg.data, receivedAt: Date.now() },
        ...state.events,
      ].slice(0, MAX_EVENTS);
      emit();
    } catch {

    }
  };

  ws.onclose = (ev) => {
    if (socket === ws) {
      socket = null;
      state.connected = false;
      emit();
    }
    if (ev.code === 4401 || ev.code === 1008) {
      authFailed = true;
      return;
    }
    scheduleReconnect();
  };

  ws.onerror = () => {
    ws.close();
  };
}

function scheduleReconnect() {
  if (retryTimer !== null || listeners.size === 0 || authFailed) return;
  reconnectAttempt += 1;
  const delay = Math.min(1000 * 2 ** reconnectAttempt, 15000);
  retryTimer = window.setTimeout(() => {
    retryTimer = null;
    connect();
  }, delay);
}

function startPing() {
  if (pingTimer !== null) return;
  pingTimer = window.setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) socket.send('ping');
  }, 25000);
}

export function subscribeSecurityFeed(listener: Listener): () => void {
  listeners.add(listener);
  listener({ connected: state.connected, events: state.events, revision: state.revision });
  if (listeners.size === 1) {
    connect();
    startPing();
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      if (pingTimer !== null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (socket) {
        socket.close();
        socket = null;
        state.connected = false;
      }
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
    }
  };
}
