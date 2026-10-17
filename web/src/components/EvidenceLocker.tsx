import type { ClueEntry, SuspectCard } from "../types";

interface Props {
  clues: ClueEntry[];
  fresh: Set<string>;
  selected: Set<string>;
  onToggle: (id: string) => void;
  focus: SuspectCard | null;
  onPresent: () => void;
  disabled?: boolean;
}

export function EvidenceLocker({ clues, fresh, selected, onToggle, focus, onPresent, disabled }: Props) {
  const canPresent = !!focus && selected.size > 0 && !disabled;
  return (
    <section aria-labelledby="locker-heading" className="flex h-full min-h-0 flex-col">
      <div className="flex items-baseline justify-between px-4 pt-4 pb-3">
        <h2 id="locker-heading" className="font-display text-xl font-semibold">
          Evidence locker
        </h2>
        <span className="label">{clues.length} / 24</span>
      </div>

      {clues.length === 0 ? (
        <p className="px-4 text-sm leading-relaxed text-muted">
          Nothing logged yet. Clues land here when the scene, the records desk or forensics
          turns something up. Suspects' words don't count as evidence.
        </p>
      ) : (
        <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 pb-4">
          {clues.map((c) => {
            const isSel = selected.has(c.id);
            return (
              <li key={c.id} className={fresh.has(c.id) ? "rise" : ""}>
                <label
                  className={`block cursor-pointer rounded-sm border p-3 transition-colors ${
                    isSel ? "border-amber bg-raised" : "border-line bg-panel hover:border-muted"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="h-3.5 w-3.5 accent-[var(--color-amber)]"
                      checked={isSel}
                      onChange={() => onToggle(c.id)}
                      aria-label={`Select clue ${c.id}`}
                    />
                    <span className="font-mono text-xs text-amber">{c.id}</span>
                    <span className="truncate font-mono text-[11px] text-dim">{c.source_title}</span>
                    {fresh.has(c.id) && (
                      <span className="ml-auto font-mono text-[10px] uppercase tracking-widest text-amber">
                        new
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 font-mono text-[12px] leading-relaxed text-paper/90">
                    {c.notebook}
                  </p>
                </label>
              </li>
            );
          })}
        </ul>
      )}

      <div className="border-t border-line p-4">
        <button type="button" className="btn btn-amber w-full" disabled={!canPresent} onClick={onPresent}>
          {focus
            ? `Present ${selected.size || ""} to ${focus.name.split(" ")[0]}`.replace("  ", " ")
            : "Select a suspect to present"}
        </button>
        {focus && selected.size === 0 && (
          <p className="mt-2 text-center text-xs text-dim">Tick clues above to show them.</p>
        )}
      </div>
    </section>
  );
}
