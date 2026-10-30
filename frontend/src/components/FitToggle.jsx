const OPTIONS = [
  { value: "cover", label: "Cover", hint: "Penuh, crop sisi berlebih" },
  { value: "contain", label: "Contain", hint: "Utuh, boleh ada bar hitam" },
];

export default function FitToggle({ value, onChange, disabled }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={`rounded-lg border px-3 py-2 text-left transition ${
            value === o.value
              ? "border-ember-500 bg-ember-500/10 text-white"
              : "border-ink-600 bg-ink-900 text-stone-400 hover:border-ember-500/40"
          }`}
        >
          <span className="block text-sm font-semibold">{o.label}</span>
          <span className="block text-[11px] text-stone-500">{o.hint}</span>
        </button>
      ))}
    </div>
  );
}
