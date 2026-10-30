import { Plus, Trash2 } from "lucide-react";
import TimeInput from "./TimeInput.jsx";

let seq = 0;
const newRow = () => ({ id: ++seq, start: "", end: "" });

export default function MuteRangesEditor({ rows, onChange, disabled }) {
  const list = rows.length ? rows : [newRow()];

  const update = (id, key, value) => onChange(list.map((r) => (r.id === id ? { ...r, [key]: value } : r)));
  const remove = (id) => onChange(list.length > 1 ? list.filter((r) => r.id !== id) : [newRow()]);
  const add = () => onChange([...list, newRow()]);

  return (
    <div className="space-y-2">
      {list.map((row, i) => (
        <div key={row.id} className="flex items-center gap-2">
          <span className="w-5 shrink-0 text-xs text-stone-500">{i + 1}.</span>
          <TimeInput value={row.start} onChange={(v) => update(row.id, "start", v)} disabled={disabled} />
          <span className="text-stone-500">—</span>
          <TimeInput value={row.end} onChange={(v) => update(row.id, "end", v)} disabled={disabled} />
          <button type="button" className="btn-ghost !px-2.5 !py-2" onClick={() => remove(row.id)} disabled={disabled} title="Hapus rentang">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
      <button type="button" className="btn-ghost" onClick={add} disabled={disabled || list.length >= 10}>
        <Plus className="h-4 w-4" /> Tambah rentang
      </button>
      <p className="text-[11px] text-stone-500">Waktu dihitung dari awal CLIP (00:00), bukan dari video sumber utuh.</p>
    </div>
  );
}
