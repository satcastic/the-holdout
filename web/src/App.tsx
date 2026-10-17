import { useCallback, useMemo, useRef, useState } from "react";
import { accuse, createSession, sendTurn } from "./api";
import { AccuseModal } from "./components/AccuseModal";
import { Briefing } from "./components/Briefing";
import { EvidenceLocker } from "./components/EvidenceLocker";
import { Interrogation } from "./components/Interrogation";
import { SuspectList } from "./components/SuspectList";
import { VerdictScreen } from "./components/VerdictScreen";
import type { Action, GameStatus, SessionCreated, TranscriptEntry, Verdict } from "./types";

type Tab = "suspects" | "talk" | "evidence";

const CHANNEL_LABEL = {
  examine_scene: "Examine Server Room 11-S",
  request_records: "Request records",
  ask_forensics: "Ask forensics",
} as const;

export default function App() {
  const [session, setSession] = useState<SessionCreated | null>(null);
  const [status, setStatus] = useState<GameStatus | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [streaming, setStreaming] = useState<{ speaker: string; text: string } | null>(null);
  const [statusLabel, setStatusLabel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [accuseOpen, setAccuseOpen] = useState(false);
  const [lastFeedback, setLastFeedback] = useState<string | null>(null);
  const [ending, setEnding] = useState<{ verdict: Verdict; reply: string } | null>(null);
  // Set when the case closes, however the accusation was made (button or typed text).
  const [closing, setClosing] = useState<{ verdict: Verdict; reply: string } | null>(null);
  const [tab, setTab] = useState<Tab>("talk");
  const nextId = useRef(1);

  const push = useCallback((speaker: string, text: string) => {
    const id = nextId.current++;
    setTranscript((t) => [...t, { id, speaker, text }]);
    return id;
  }, []);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const s = await createSession();
      setSession(s);
      setStatus({
        session_id: s.session_id,
        turns_left: s.turns_left,
        start_turns: s.start_turns,
        discovered: [],
        suspects_questioned: [],
        current_focus: null,
        accusations_left: 2,
        game_over: false,
        verdict: null,
      });
      nextId.current = 1;
      setTranscript([{ id: nextId.current++, speaker: "narrator", text: s.intro }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the precinct. Is the API running?");
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    setSession(null);
    setStatus(null);
    setTranscript([]);
    setFocus(null);
    setSelected(new Set());
    setFresh(new Set());
    setEnding(null);
    setClosing(null);
    setLastFeedback(null);
  };

  const runTurn = async (playerText: string, text: string, action: Action | null) => {
    if (!session || busy) return;
    setBusy(true);
    setError(null);
    setStatusLabel("Reading your notes");
    push("player", playerText);
    let replyId: number | null = null;
    let lastReply = "";
    try {
      await sendTurn(session.session_id, text, action, {
        onStatus: setStatusLabel,
        onReplyStart: (speaker) => setStreaming({ speaker, text: "" }),
        onToken: (tok) => setStreaming((s) => (s ? { ...s, text: s.text + tok } : s)),
        onReplyEnd: (speaker, full) => {
          setStreaming(null);
          lastReply = full;
          replyId = push(speaker, full);
        },
        onState: (st) => {
          setStatus(st);
          if (st.new_clues.length) {
            setFresh(new Set(st.new_clues.map((c) => c.id)));
            const id = replyId;
            setTranscript((t) => t.map((e) => (e.id === id ? { ...e, newClues: st.new_clues } : e)));
          }
          if (st.current_focus && st.current_focus !== focus) setFocus(st.current_focus);
          if (st.game_over && st.verdict) {
            const closed = { verdict: st.verdict, reply: lastReply };
            setClosing(closed);
            // Give the player a moment to read the DA's reply, then open the verdict.
            window.setTimeout(() => setEnding(closed), 2500);
          }
        },
      });
    } catch (e) {
      setStreaming(null);
      setError(e instanceof Error ? e.message : "The line went dead.");
    } finally {
      setBusy(false);
      setStatusLabel(null);
    }
  };

  const suspectById = useMemo(
    () => Object.fromEntries((session?.suspects ?? []).map((s) => [s.id, s])),
    [session],
  );
  const focusCard = focus ? suspectById[focus] ?? null : null;

  const onSend = (text: string) => {
    // A selected suspect turns typed text into a structured action (skips the router LLM).
    const action: Action | null = focus ? { kind: "question_suspect", suspect_id: focus } : null;
    runTurn(text, text, action);
  };

  const onChannel = (kind: keyof typeof CHANNEL_LABEL, text: string) => {
    setFocus(null);
    runTurn(text ? `${CHANNEL_LABEL[kind]}: ${text}` : `${CHANNEL_LABEL[kind]}.`, text, { kind });
  };

  const onPresent = () => {
    if (!focus || selected.size === 0) return;
    const ids = [...selected];
    runTurn(`Present ${ids.join(", ")} to ${suspectById[focus].name}.`, "", {
      kind: "present_evidence",
      suspect_id: focus,
      clue_ids: ids,
    });
    setSelected(new Set());
    setTab("talk");
  };

  const toggleClue = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const onAccuse = async (suspectId: string, reasoning: string, clueIds: string[]) => {
    if (!session) return;
    const res = await accuse(session.session_id, suspectId, reasoning, clueIds);
    setStatus(res.state);
    push("player", `I accuse ${suspectById[suspectId].name}.${reasoning ? " " + reasoning : ""}`);
    push("narrator", res.reply);
    if (res.state.game_over) {
      setAccuseOpen(false);
      setClosing({ verdict: res.verdict, reply: res.reply });
      setEnding({ verdict: res.verdict, reply: res.reply });
    } else {
      setLastFeedback(res.reply);
    }
  };

  if (!session || !status) return <Briefing onStart={start} starting={starting} error={error} />;
  if (ending) return <VerdictScreen sessionId={session.session_id} verdict={ending.verdict} reply={ending.reply} onNewCase={reset} />;

  const turnPct = (status.turns_left / status.start_turns) * 100;
  const outOfTurns = status.turns_left <= 0;

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-ink/90 px-4 py-3 sm:px-5">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-2xl font-semibold leading-none">{session.title}</h1>
          <span className="label hidden md:inline">Veridia AI · Harlan Building</span>
        </div>
        <div className="ml-auto flex items-center gap-5">
          <div className="w-36" aria-label={`${status.turns_left} moves left of ${status.start_turns}`}>
            <div className="flex justify-between">
              <span className="label">Moves left</span>
              <span className={`font-mono text-xs ${status.turns_left <= 5 ? "text-blood" : "text-amber"}`}>
                {status.turns_left}
              </span>
            </div>
            <div className="mt-1 h-1 bg-raised">
              <div
                className={`h-full transition-all ${status.turns_left <= 5 ? "bg-blood" : "bg-amber"}`}
                style={{ width: `${turnPct}%` }}
              />
            </div>
          </div>
          {status.game_over && closing ? (
            <button type="button" className="btn btn-amber" onClick={() => setEnding(closing)}>
              See the verdict
            </button>
          ) : (
            <button
              type="button"
              className="btn border-blood text-blood hover:bg-blood hover:text-paper"
              onClick={() => setAccuseOpen(true)}
              disabled={busy || status.game_over}
            >
              Accuse
            </button>
          )}
        </div>
      </header>

      {error && (
        <div role="alert" className="flex items-center justify-between border-b border-blood/50 bg-blood/15 px-5 py-2 text-sm">
          <span>{error}</span>
          <button type="button" className="text-xs underline" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      <nav className="grid grid-cols-3 border-b border-line lg:hidden" aria-label="Panels">
        {(["suspects", "talk", "evidence"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            aria-pressed={tab === t}
            className={`py-2.5 text-xs uppercase tracking-widest ${tab === t ? "border-b-2 border-amber text-amber" : "text-muted"}`}
          >
            {t === "talk" ? "Interrogation" : t === "evidence" ? `Evidence (${status.discovered.length})` : "Suspects"}
          </button>
        ))}
      </nav>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <aside className={`${tab === "suspects" ? "block" : "hidden"} min-h-0 overflow-y-auto border-line lg:block lg:border-r`}>
          <SuspectList
            suspects={session.suspects}
            questioned={status.suspects_questioned}
            focus={focus}
            disabled={busy}
            onSelect={(id) => {
              setFocus(id);
              if (id) setTab("talk");
            }}
          />
        </aside>
        <main className={`${tab === "talk" ? "flex" : "hidden"} min-h-0 flex-col lg:flex`}>
          <Interrogation
            transcript={transcript}
            streaming={streaming}
            statusLabel={statusLabel}
            busy={busy}
            focus={focusCard}
            suspects={session.suspects}
            outOfTurns={outOfTurns}
            onSend={onSend}
            onChannel={onChannel}
          />
        </main>
        <aside className={`${tab === "evidence" ? "flex" : "hidden"} min-h-0 flex-col border-line lg:flex lg:border-l`}>
          <EvidenceLocker
            clues={status.discovered}
            fresh={fresh}
            selected={selected}
            onToggle={toggleClue}
            focus={focusCard}
            onPresent={onPresent}
            disabled={busy || outOfTurns}
          />
        </aside>
      </div>

      {accuseOpen && (
        <AccuseModal
          suspects={session.suspects}
          clues={status.discovered}
          preselected={selected}
          accusationsLeft={status.accusations_left}
          lastFeedback={lastFeedback}
          onSubmit={onAccuse}
          onClose={() => setAccuseOpen(false)}
        />
      )}
    </div>
  );
}
