import { useRef, useState } from "react";
import { CheckCircle2, FileVideo, Loader2, UploadCloud, X } from "lucide-react";
import { formatBytes } from "../utils/time.js";

const ACCEPT = ".mp4,.mkv,.mov,.webm";

export default function UploadZone({ state, onFile, onClear, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const { status, progress, info, fileName } = state;

  const pick = (file) => {
    if (file && !disabled) onFile(file);
  };

  if (status === "done" && info) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
        <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-400" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-stone-100">{info.filename}</p>
          <p className="text-xs text-stone-400">
            Duration: <span className="font-mono text-gold-300">{info.duration_text}</span> · {info.width}×{info.height} ·{" "}
            {formatBytes(info.size)} · {info.has_audio ? "audio ✓" : "tanpa audio"}
          </p>
        </div>
        <button className="btn-ghost !px-2.5 !py-2" onClick={onClear} disabled={disabled} title="Ganti video">
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  if (status === "uploading") {
    return (
      <div className="rounded-xl border border-ember-500/30 bg-ink-900 p-4">
        <div className="mb-2 flex items-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin text-ember-400" />
          <span className="truncate font-medium text-stone-200">{fileName}</span>
          <span className="ml-auto font-mono text-gold-300">{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-ink-600">
          <div className="h-full rounded-full bg-gradient-to-r from-ember-600 to-gold-400 transition-all" style={{ width: `${progress}%` }} />
        </div>
        {progress >= 100 && <p className="mt-2 text-xs text-stone-500">Memeriksa video…</p>}
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
      className={`rounded-xl border-2 border-dashed p-6 text-center transition ${
        dragging ? "border-ember-500 bg-ember-500/10" : "border-ink-600 bg-ink-900 hover:border-ember-500/50"
      }`}
    >
      <FileVideo className="mx-auto mb-2 h-9 w-9 text-ember-400/80" />
      <p className="text-sm text-stone-300">Tarik &amp; lepas video konten video di sini</p>
      <p className="mb-3 text-xs text-stone-500">mp4, mkv, mov, webm</p>
      <button type="button" className="btn-primary !py-2.5" onClick={() => inputRef.current?.click()} disabled={disabled}>
        <UploadCloud className="h-4 w-4" /> Upload Video
      </button>
      <input ref={inputRef} type="file" accept={ACCEPT} className="hidden"
        onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      {status === "error" && state.error && <p className="mt-3 text-sm text-red-400">{state.error}</p>}
    </div>
  );
}
