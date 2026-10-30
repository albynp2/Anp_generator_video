import { useState } from "react";
import { Download, Flame, Film, Trash2 } from "lucide-react";
import ProgressBar from "./ProgressBar.jsx";
import { deleteJob, downloadUrl, previewUrl, templatePreviewUrl } from "../services/api.js";

export default function PreviewPanel({
  job, template, sourcePreviewUrl, fit = "cover", videoArea, templateWidth = 1080, templateHeight = 1920,
  startSeconds = 0, endSeconds, retentionMinutes, outputWidth = 1080, outputHeight = 1920, onDeleted
}) {
  const [deleting, setDeleting] = useState(false);
  const status = job?.status;
  const busy = status === "queued" || status === "processing";
  const done = status === "completed";
  const area = videoArea || { x: 0, y: outputHeight * 0.15, width: outputWidth, height: outputHeight * 0.7 };
  const areaStyle = {
    left: `${(area.x / templateWidth) * 100}%`,
    top: `${(area.y / templateHeight) * 100}%`,
    width: `${(area.width / templateWidth) * 100}%`,
    height: `${(area.height / templateHeight) * 100}%`,
  };

  const remove = async () => {
    setDeleting(true);
    try { await deleteJob(job.job_id); } catch { /* sudah terhapus otomatis */ }
    setDeleting(false);
    onDeleted?.();
  };

  return (
    <div className="panel p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-gold-400">
        <Film className="h-4 w-4" /> Preview
      </div>

      <div className="relative mx-auto w-full max-w-[380px] overflow-hidden rounded-xl border border-ink-600 bg-black" style={{ aspectRatio: `${outputWidth} / ${outputHeight}` }}>
        {done ? (
          <video key={job.job_id} className="h-full w-full bg-black object-contain" src={previewUrl(job.job_id)} controls playsInline autoPlay loop />
        ) : (
          <>
            {template && <img src={templatePreviewUrl(template)} alt="Preview template tersimpan" className={`absolute inset-0 h-full w-full object-fill ${busy ? "opacity-40 blur-[1px]" : "opacity-100"}`} />}
            {sourcePreviewUrl && template && (
              <video
                key={sourcePreviewUrl}
                src={sourcePreviewUrl}
                className="absolute"
                style={{ ...areaStyle, objectFit: fit === "contain" ? "contain" : "cover" }}
                muted
                playsInline
                autoPlay
                onLoadedMetadata={(event) => { event.currentTarget.currentTime = Math.max(0, startSeconds); }}
                onTimeUpdate={(event) => { if (endSeconds > startSeconds && event.currentTarget.currentTime >= endSeconds) event.currentTarget.currentTime = Math.max(0, startSeconds); }}
              />
            )}
            {busy && <div className="absolute inset-0 z-10 grid place-items-center bg-black/20"><Flame className="h-10 w-10 animate-pulse text-ember-400" /></div>}
          </>
        )}
      </div>

      {sourcePreviewUrl && !done && (
        <p className="mt-2 text-center text-[11px] text-stone-500">Preview langsung · Video Fit: {fit === "contain" ? "Contain" : "Cover"}</p>
      )}

      {busy && <div className="mt-4"><ProgressBar label={status === "queued" ? "Menunggu antrean" : job.stage || "Rendering Video"} percent={job.progress} /></div>}

      {done && (
        <div className="mt-4 space-y-2">
          <a href={downloadUrl(job.job_id)} className="btn-primary w-full" download={job.filename}>
            <Download className="h-4 w-4" /> Download Clip
          </a>
          <p className="text-center font-mono text-xs text-stone-500">{job.filename}</p>
          <button className="btn-ghost w-full" onClick={remove} disabled={deleting} title="Hapus video & caption dari server sekarang">
            <Trash2 className="h-4 w-4" /> {deleting ? "Menghapus…" : "Hapus dari server"}
          </button>
          {retentionMinutes ? <p className="text-center text-[11px] text-amber-300/80">Hasil tidak disimpan permanen — dihapus otomatis ±{retentionMinutes} menit setelah selesai. Download sekarang.</p> : null}
        </div>
      )}
    </div>
  );
}
