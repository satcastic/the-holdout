import { useEffect, useRef, useState } from "react";
import type { SuspectCard, TranscriptEntry } from "../types";

interface Props {
  transcript: TranscriptEntry[];
  streaming: { speaker: string; text: string } | null;
  statusLabel: string | null;
  busy: boolean;
  focus: SuspectCard | null;
  suspects: SuspectCard[];
  outOfTurns: boolean;
  onSend: (text: string) => void;
  onChannel: (kind: "examine_scene" | "request_records" | "ask_forensics", text: string) => void;
}

const CHANNEL_NAMES: Record<string, string> = {
  narrator: "Narrator",
  records: "Records desk",
  scene: "Scene",
  forensics: "Forensics",
  player: "You",
};

export function speakerName(speaker: string, suspects: SuspectCard[]) {
  return CHANNEL_NAMES[speaker] ?? suspects.find((s) => s.id === speaker)?.name ?? speaker;
}

export function Interrogation({
  transcript,
  streaming,
  statusLabel,
  busy,
  focus,
  suspects,
  outOfTurns,
  onSend,
  onChannel,
}: Props) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript.length, streaming?.text, statusLabel]);

  useEffect(() => {
    if (!busy) inputRef.current?.focus();
  }, [busy, focus?.id]);

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText("");
  };

  const channel = (kind: "examine_scene" | "request_records" | "ask_forensics") => {
    onChannel(kind, text.trim());
    setText("");
  };

  const placeholder = outOfTurns
    ? "Out of moves. Make your accusation."
    : focus
      ? `Ask ${focus.name.split(" ")[0]} something…`
      : "Ask anything, or pick a suspect on the left…";

  return (
    <section aria-label="Interrogation" className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <div>
          <div className="label">{focus ? "Interview room" : "Case desk"}</div>
          <div className="font-display text-2xl leading-tight">
            {focus ? focus.name : "Open investigation"}
          </div>
        </div>
        {focus && <div className="hidden text-right text-xs text-muted sm:block">{focus.role}</div>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4" aria-live="polite" aria-relevant="additions">
        <ol className="space-y-5">
          {transcript.map((e) => (
            <li key={e.id} className={`rise ${e.speaker === "player" ? "pl-6 sm:pl-16" : "pr-6 sm:pr-16"}`}>
              <Entry entry={e} suspects={suspects} />
            </li>
          ))}
          {streaming && (
            <li className="pr-6 sm:pr-16">
              <Entry entry={{ id: -1, speaker: streaming.speaker, text: streaming.text }} suspects={suspects} live />
            </li>
          )}
        </ol>
        {busy && statusLabel && !streaming && (
          <p className="mt-5 flex items-center gap-2 font-mono text-xs text-amber" role="status">
            <span>{statusLabel}</span>
            <span aria-hidden>
              <span className="dot">.</span>
              <span className="dot">.</span>
              <span className="dot">.</span>
            </span>
          </p>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-line p-4">
        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Quick actions">
          <button type="button" className="chip" disabled={busy || outOfTurns} onClick={() => channel("examine_scene")}>
            Examine Server Room 11-S
          </button>
          <button type="button" className="chip" disabled={busy || outOfTurns} onClick={() => channel("request_records")}>
            Request records
          </button>
          <button type="button" className="chip" disabled={busy || outOfTurns} onClick={() => channel("ask_forensics")}>
            Ask forensics
          </button>
          <span className="self-center text-[11px] text-dim">
            Text in the box becomes the request.
          </span>
        </div>
        <form
          className="flex items-end gap-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            submit();
          }}
        >
          <label htmlFor="ask" className="sr-only">
            Your question
          </label>
          <textarea
            id="ask"
            ref={inputRef}
            rows={2}
            maxLength={1000}
            value={text}
            disabled={outOfTurns}
            placeholder={placeholder}
            onChange={(ev) => setText(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" && !ev.shiftKey) {
                ev.preventDefault();
                submit();
              }
            }}
            className="min-h-[3rem] flex-1 resize-none rounded-sm border border-line bg-ink px-3 py-2 text-sm text-paper placeholder:text-dim focus:border-amber focus:outline-none disabled:opacity-50"
          />
          <button type="submit" className="btn btn-amber h-12 px-5" disabled={busy || !text.trim() || outOfTurns}>
            {busy ? "…" : "Ask"}
          </button>
        </form>
      </div>
    </section>
  );
}

function Entry({ entry, suspects, live }: { entry: TranscriptEntry; suspects: SuspectCard[]; live?: boolean }) {
  const isPlayer = entry.speaker === "player";
  const isChannel = ["records", "scene", "forensics"].includes(entry.speaker);
  const isNarrator = entry.speaker === "narrator";
  return (
    <div>
      <div className={`label mb-1 ${isPlayer ? "text-right" : ""} ${isChannel ? "text-amber/80" : ""}`}>
        {speakerName(entry.speaker, suspects)}
      </div>
      <div
        className={
          isPlayer
            ? "ml-auto w-fit max-w-full rounded-sm border border-line bg-raised px-3 py-2 text-sm"
            : isChannel
              ? "whitespace-pre-wrap border-l-2 border-amber/60 pl-3 font-mono text-[12.5px] leading-relaxed text-paper/90"
              : isNarrator
                ? "font-display text-lg italic leading-snug text-muted"
                : "font-display text-[1.2rem] leading-snug"
        }
      >
        {entry.text}
        {live && <span className="ml-0.5 inline-block w-2 animate-pulse text-amber">▍</span>}
      </div>
      {entry.newClues && entry.newClues.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {entry.newClues.map((c) => (
            <span key={c.id} className="rounded-sm border border-amber/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-amber">
              + {c.id} logged
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
