import type { AccuseResult, Action, GameStatus, Reveal, SessionCreated, TurnState } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new ApiError(res.status, await errorText(res));
  return res.json() as Promise<T>;
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  if (res.status === 429) return "Slow down, detective. Try again in a minute.";
  return `Request failed (${res.status})`;
}

export const createSession = () => json<SessionCreated>("/api/sessions", { method: "POST" });
export const getState = (sid: string) => json<GameStatus>(`/api/sessions/${sid}/state`);
export const getReveal = (sid: string) => json<Reveal>(`/api/sessions/${sid}/reveal`);
export const accuse = (sid: string, suspect_id: string, reasoning: string, clue_ids: string[]) =>
  json<AccuseResult>(`/api/sessions/${sid}/accuse`, {
    method: "POST",
    body: JSON.stringify({ suspect_id, reasoning, clue_ids }),
  });

export interface TurnHandlers {
  onStatus: (label: string) => void;
  onReplyStart: (speaker: string) => void;
  onToken: (text: string) => void;
  onReplyEnd: (speaker: string, text: string) => void;
  onState: (state: TurnState) => void;
}

/** POST a turn and consume the SSE stream (EventSource cannot POST, so parse by hand). */
export async function sendTurn(
  sid: string,
  text: string,
  action: Action | null,
  h: TurnHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/sessions/${sid}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ text, action }),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, await errorText(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      dispatch(block, h);
    }
  }
}

function dispatch(block: string, h: TurnHandlers) {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return;
  const payload = JSON.parse(data.join("\n"));
  switch (event) {
    case "status":
      h.onStatus(payload.label);
      break;
    case "reply_start":
      h.onReplyStart(payload.speaker);
      break;
    case "token":
      h.onToken(payload.text);
      break;
    case "reply_end":
      h.onReplyEnd(payload.speaker, payload.text);
      break;
    case "state":
      h.onState(payload as TurnState);
      break;
    case "error":
      throw new ApiError(500, payload.message);
  }
}
