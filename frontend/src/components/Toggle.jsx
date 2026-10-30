export default function Toggle({ checked, onChange, disabled, label, hint }) {
  return (
    <div className="flex items-start gap-3">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full border transition ${
          checked ? "border-ember-500 bg-ember-600" : "border-ink-600 bg-ink-700"
        } disabled:opacity-50`}
      >
        <span
          className={`absolute top-0.5 h-4.5 w-[18px] rounded-full bg-white shadow transition-all ${
            checked ? "left-[22px]" : "left-0.5"
          }`}
          style={{ height: 18 }}
        />
      </button>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-stone-100">
          {label} <span className={`ml-1 text-xs font-bold ${checked ? "text-emerald-400" : "text-stone-500"}`}>{checked ? "ON" : "OFF"}</span>
        </p>
        {hint && <p className="text-xs text-stone-500">{hint}</p>}
      </div>
    </div>
  );
}
