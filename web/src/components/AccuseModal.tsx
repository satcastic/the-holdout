import { useEffect, useRef, useState } from "react";
import type { ClueEntry, SuspectCard } from "../types";

interface Props {
  suspects: SuspectCard[];
  clues: ClueEntry[];
  preselected: Set<string>;
  accusationsLeft: number;
  lastFeedback: string | null;
  onSubmit: (suspectId: string, reasoning: string, clueIds: string[]) => Promise<void>;
  onClose: () => void;
}

export function AccuseModal({ suspects, clues, preselected, accusationsLeft, lastFeedback, onSubmit, onClose }: Props) {
  const [suspect, setSuspect] = useState<string>("");
  const [reasoning, setReasoning] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set(preselected));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>("input, textarea, button")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
      if (e.key === "Tab" && dialogRef.current) {
        const items = dialogRef.current.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), textarea:not([disabled])",
        );
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [busy, onClose]);

  const toggle = (id: string) =>
    setPicked((p) => {
      const n = new Set(p);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const submit = async () => {
    if (!suspect) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(suspect, reasoning.trim(), [...picked]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-6" onClick={() => !busy && onClose()}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="accuse-title"
        onClick={(e) => e.stopPropagation()}
        className="panel flex max-h-[92vh] w-full max-w-2xl flex-col bg-panel"
      >
        <header className="border-b border-line px-6 py-4">
          <div className="label text-blood">Formal accusation</div>
          <h2 id="accuse-title" className="font-display text-3xl">Name your suspect</h2>
          <p className="mt-1 text-xs text-muted">
            {accusationsLeft} wrong accusation{accusationsLeft === 1 ? "" : "s"} left before you're off the case.
            Only clues in your locker count.
          </p>
        </header>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {lastFeedback && (
            <p className="border-l-2 border-blood pl-3 font-display text-lg italic text-muted">{lastFeedback}</p>
          )}
          <fieldset>
            <legend className="label mb-2">Suspect</legend>
            <div className="grid grid-cols-2 gap-2">
              {suspects.map((s) => (
                <label
                  key={s.id}
                  className={`cursor-pointer rounded-sm border p-3 transition-colors ${
                    suspect === s.id ? "border-blood bg-raised" : "border-line hover:border-muted"
                  }`}
                >
                  <input
                    type="radio"
                    name="suspect"
                    value={s.id}
                    checked={suspect === s.id}
                    onChange={() => setSuspect(s.id)}
                    className="sr-only"
                  />
                  <div className="font-display text-lg leading-tight">{s.name}</div>
                  <div className="truncate text-xs text-muted">{s.role}</div>
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="reasoning" className="label mb-2 block">
              Your reasoning
            </label>
            <textarea
              id="reasoning"
              rows={5}
              maxLength={4000}
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              placeholder="Opportunity, broken alibi, who you ruled out and why, motive…"
              className="w-full resize-y rounded-sm border border-line bg-ink px-3 py-2 text-sm placeholder:text-dim focus:border-amber focus:outline-none"
            />
          </div>

          <fieldset>
            <legend className="label mb-2">Supporting evidence ({picked.size})</legend>
            {clues.length === 0 ? (
              <p className="text-sm text-dim">Your locker is empty.</p>
            ) : (
              <ul className="space-y-1.5">
                {clues.map((c) => (
                  <li key={c.id}>
                    <label className="flex cursor-pointer gap-2 rounded-sm p-1.5 hover:bg-raised">
                      <input
                        type="checkbox"
                        checked={picked.has(c.id)}
                        onChange={() => toggle(c.id)}
                        className="mt-0.5 h-3.5 w-3.5 accent-[var(--color-amber)]"
                      />
                      <span className="font-mono text-xs text-amber">{c.id}</span>
                      <span className="font-mono text-xs leading-relaxed text-paper/85">{c.notebook}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>
          {error && (
            <p role="alert" className="text-sm text-blood">
              {error}
            </p>
          )}
        </div>

        <footer className="flex justify-end gap-2 border-t border-line px-6 py-4">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Not yet
          </button>
          <button
            type="button"
            className="btn border-blood bg-blood text-paper hover:bg-blood/80"
            disabled={!suspect || busy}
            onClick={submit}
          >
            {busy ? "The DA is reading…" : "Make the accusation"}
          </button>
        </footer>
      </div>
    </div>
  );
}
