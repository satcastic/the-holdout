interface Props {
  onStart: () => void;
  starting: boolean;
  error: string | null;
}

export function Briefing({ onStart, starting, error }: Props) {
  return (
    <main className="flex min-h-full items-center justify-center px-5 py-12">
      <div className="w-full max-w-2xl">
        <div className="label">San Francisco PD · Homicide · SoMa</div>
        <h1 className="mt-3 font-display text-6xl font-semibold leading-none sm:text-7xl">The Holdout</h1>
        <div className="mt-6 h-px w-24 bg-amber" aria-hidden />
        <p className="mt-6 font-display text-2xl leading-snug text-paper/90">
          Hours before she was due to blow the whistle on a hidden flaw in TriageOne, Veridia AI's
          lead systems architect is found dead in a latched server room.
        </p>
        <p className="mt-4 leading-relaxed text-muted">
          The Series C closes on Monday. Four people had every reason to want her silent. You
          have a limited number of moves: question suspects, show them evidence, walk the scene,
          pull records and call the lab. Then name the person who did it, and prove it.
        </p>
        <dl className="mt-8 grid grid-cols-2 gap-4 border-y border-line py-5 text-sm sm:grid-cols-3">
          <div>
            <dt className="label">Victim</dt>
            <dd className="mt-1">Elena Voss, 41</dd>
          </div>
          <div>
            <dt className="label">Found</dt>
            <dd className="mt-1 font-mono text-xs">2026-11-13 06:15</dd>
          </div>
          <div>
            <dt className="label">Where</dt>
            <dd className="mt-1">Server Room 11-S</dd>
          </div>
        </dl>
        <button type="button" className="btn btn-amber mt-8 px-6 py-3 text-base" onClick={onStart} disabled={starting}>
          {starting ? "Pulling the file…" : "Take the case"}
        </button>
        {error && (
          <p role="alert" className="mt-4 text-sm text-blood">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
