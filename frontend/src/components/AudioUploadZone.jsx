import { useRef } from "react";
import { CheckCircle2, Loader2, Music, UploadCloud, X } from "lucide-react";

export default function AudioUploadZone({ state, onFile, onClear, disabled }) {
  const inputRef = useRef(null);
  const { status, progress, info, error } = state;

  if (status === "done" && info) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-stone-100">{info.filename}</p>
          <p className="text-xs text-stone-400">Durasi: <span className="font-mono text-gold-300">{info.duration_text}</span> — otomatis diulang bila lebih pendek dari rentang mute</p>
        </div>
        <button className="btn-ghost !px-2.5 !py-2" onClick={onClear} disabled={disabled}>
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  if (status === "uploading") {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-ember-500/30 bg-ink-900 p-3 text-sm">
        <Loader2 className="h-4 w-4 animate-spin text-ember-400" /> Mengupload musik… <span className="ml-auto font-mono text-gold-300">{progress}%</span>
      </div>
    );
  }

  return (
    <div>
      <button type="button" className="btn-ghost w-full justify-center" onClick={() => inputRef.current?.click()} disabled={disabled}>
        <UploadCloud className="h-4 w-4" /> <Music className="h-4 w-4" /> Upload Musik Pengganti
      </button>
      <input ref={inputRef} type="file" accept=".mp3,.wav,.m4a,.aac,.ogg" className="hidden"
        onChange={(e) => { if (e.target.files?.[0]) onFile(e.target.files[0]); e.target.value = ""; }} />
      {status === "error" && error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </div>
  );
}
