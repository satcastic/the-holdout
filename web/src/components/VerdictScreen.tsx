import { useEffect, useState } from "react";
import { getReveal } from "../api";
import type { Reveal, Verdict } from "../types";

interface Props {
  sessionId: string;
  verdict: Verdict;
  reply: string;
  onNewCase: () => void;
}

const GRADES: Record<Verdict["grade"], { title: string; tone: string }> = {
  full_credit: { title: "Case closed", tone: "text-amber" },
  partial_credit: { title: "Right name, thin case", tone: "text-amber" },
  wrong: { title: "Wrong suspect", tone: "text-blood" },
  case_lost: { title: "Off the case", tone: "text-blood" },
};

const PARTS: { key: keyof Verdict["breakdown"]; label: string; max: number }[] = [
  { key: "suspect", label: "Correct suspect", max: 40 },
  { key: "alibi", label: "Alibi broken", max: 20 },
  { key: "eliminations", label: "Others ruled out", max: 20 },
  { key: "motive", label: "Motive", max: 10 },
  { key: "turns", label: "Moves to spare", max: 10 },
];

export function VerdictScreen({ sessionId, verdict, reply, onNewCase }: Props) {
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const g = GRADES[verdict.grade];

  useEffect(() => {
    getReveal(sessionId)
      .then(setReveal)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not open the file."));
  }, [sessionId]);

  return (
    <main className="mx-auto max-w-4xl px-5 py-10 sm:py-16">
      <div className="label">Verdict</div>
      <h1 className={`font-display text-5xl font-semibold sm:text-6xl ${g.tone}`}>{g.title}</h1>
      <p className="mt-4 max-w-2xl font-display text-xl italic leading-snug text-muted">{reply}</p>

      <section className="panel mt-10 grid gap-8 p-6 sm:grid-cols-[180px_1fr]" aria-label="Score">
        <div>
          <div className="label">Score</div>
          <div className="font-display text-7xl leading-none">
            {verdict.score}
            <span className="text-2xl text-dim">/100</span>
          </div>
          <div className="mt-2 text-sm text-muted">Accused: {verdict.accused_name}</div>
        </div>
        <ul className="space-y-3">
          {PARTS.map((p) => {
            const v = verdict.breakdown[p.key];
            return (
              <li key={p.key}>
                <div className="flex justify-between text-sm">
                  <span>{p.label}</span>
                  <span className="font-mono text-xs text-muted">
                    {v}/{p.max}
                  </span>
                </div>
                <div className="mt-1 h-1.5 bg-raised" role="presentation">
                  <div className="h-full bg-amber transition-all" style={{ width: `${(v / p.max) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="mt-12" aria-labelledby="truth-heading">
        <div className="label">The file, unsealed</div>
        <h2 id="truth-heading" className="font-display text-4xl">What really happened</h2>
        {error && <p className="mt-4 text-sm text-blood">{error}</p>}
        {!reveal && !error && <p className="mt-4 font-mono text-xs text-muted">Opening the sealed file…</p>}
        {reveal && (
          <>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <Fact label="Killer" value={reveal.killer_name} />
              <Fact label="Time of death" value={`${reveal.time_of_death}, ${reveal.location}`} />
              <Fact label="Weapon" value={reveal.weapon} />
              <Fact label="The alibi flaw" value={reveal.alibi_flaw} />
            </div>
            <p className="mt-6 leading-relaxed text-paper/90">{reveal.method}</p>
            <p className="mt-3 leading-relaxed text-muted">{reveal.staging}</p>

            <h3 className="mt-10 font-display text-2xl">The deduction</h3>
            <ol className="mt-3 space-y-2 text-sm leading-relaxed text-paper/85">
              {reveal.clue_chain.map((s) => (
                <li key={s} className="font-mono text-[12.5px]">
                  {s}
                </li>
              ))}
            </ol>

            <h3 className="mt-10 font-display text-2xl">True timeline, 2026-11-12</h3>
            <ol className="mt-4 border-l border-line">
              {reveal.timeline.map((e, i) => (
                <li key={`${e.start}-${i}`} className="relative pb-4 pl-5">
                  <span className="absolute top-1.5 -left-[4px] h-2 w-2 rounded-full bg-amber/70" aria-hidden />
                  <div className="font-mono text-xs text-amber">
                    {e.start.slice(0, 5)}–{e.end.slice(0, 5)} · {e.location}
                  </div>
                  <div className="text-sm">
                    <span className="text-muted">{e.who.join(", ")}: </span>
                    {e.event}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </section>

      <div className="mt-12">
        <button type="button" className="btn btn-amber" onClick={onNewCase}>
          Start a new investigation
        </button>
      </div>
    </main>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-line pt-3">
      <div className="label">{label}</div>
      <div className="mt-1 font-display text-xl leading-snug">{value}</div>
    </div>
  );
}
