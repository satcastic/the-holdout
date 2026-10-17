import type { SuspectCard } from "../types";

interface Props {
  suspects: SuspectCard[];
  questioned: string[];
  focus: string | null;
  onSelect: (id: string | null) => void;
  disabled?: boolean;
}

function initials(name: string) {
  return name
    .split(" ")
    .map((p) => p[0])
    .join("");
}

export function SuspectList({ suspects, questioned, focus, onSelect, disabled }: Props) {
  return (
    <section aria-labelledby="suspects-heading" className="flex h-full flex-col">
      <div className="flex items-baseline justify-between px-4 pt-4 pb-3">
        <h2 id="suspects-heading" className="font-display text-xl font-semibold">
          Suspects
        </h2>
        {focus && (
          <button
            type="button"
            className="text-xs text-muted underline-offset-4 hover:text-amber hover:underline"
            onClick={() => onSelect(null)}
          >
            Stop questioning
          </button>
        )}
      </div>
      <ul className="flex gap-3 overflow-x-auto px-4 pb-4 lg:flex-col lg:overflow-visible">
        {suspects.map((s) => {
          const active = focus === s.id;
          const asked = questioned.includes(s.id);
          return (
            <li key={s.id} className="min-w-[230px] lg:min-w-0">
              <button
                type="button"
                disabled={disabled}
                aria-pressed={active}
                onClick={() => onSelect(active ? null : s.id)}
                className={`group w-full rounded-sm border p-3 text-left transition-colors disabled:opacity-50 ${
                  active
                    ? "border-amber bg-raised"
                    : "border-line bg-panel hover:border-muted"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    aria-hidden
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-sm border font-display text-lg ${
                      active ? "border-amber text-amber" : "border-line text-muted"
                    }`}
                  >
                    {initials(s.name)}
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-lg leading-tight">{s.name}</div>
                    <div className="truncate text-xs text-muted">{s.role}</div>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted">{s.bio}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`label ${asked ? "text-amber" : ""}`}>
                    {asked ? "Questioned" : "Not yet questioned"}
                  </span>
                  {active && <span className="label text-amber">· In the room</span>}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
