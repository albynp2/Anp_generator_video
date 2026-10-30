export default function ProgressBar({ label, percent }) {
  const pct = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="font-semibold text-stone-200">{label}</span>
        <span className="font-mono text-gold-300">{pct}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-ink-600">
        <div
          className="h-full rounded-full bg-gradient-to-r from-ember-700 via-ember-500 to-gold-400 shadow-glow transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
