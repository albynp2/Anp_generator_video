import Field from "./Field.jsx";
import MuteRangesEditor from "./MuteRangesEditor.jsx";
import AudioUploadZone from "./AudioUploadZone.jsx";

// Blok "rentang waktu + pilih musik pengganti" — dipakai di mode Buat Clip Baru (di dalam toggle
// Ganti Backsound) maupun mode Ganti Backsound Saja (selalu tampil, tanpa toggle pembungkus).
export default function MuteMusicFields({
  muteRows, setMuteRows, busy, shown,
  musicMode, setMusicMode, defaultMusicAvailable,
  audioUpload, handleAudioFile, setAudioUpload, EMPTY_AUDIO,
}) {
  return (
    <>
      <div>
        <label className="label">Rentang waktu yang disenyapkan &amp; diganti</label>
        <MuteRangesEditor rows={muteRows} onChange={setMuteRows} disabled={busy} />
        {shown("muteRanges") && <p className="mt-1 text-xs text-red-400">{shown("muteRanges")}</p>}
      </div>
      <div>
        <label className="label">Musik Pengganti</label>
        <div className="mb-2 grid grid-cols-2 gap-2">
          <button type="button" disabled={busy || !defaultMusicAvailable}
            onClick={() => setMusicMode("default")}
            className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition disabled:opacity-40 ${
              musicMode === "default" ? "border-ember-500 bg-ember-500/10 text-white" : "border-ink-600 bg-ink-900 text-stone-400 hover:border-ember-500/40"
            }`}>
            Musik default
            {!defaultMusicAvailable && <span className="block text-[11px] font-normal text-stone-500">belum tersedia di server</span>}
          </button>
          <button type="button" disabled={busy}
            onClick={() => setMusicMode("upload")}
            className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition ${
              musicMode === "upload" ? "border-ember-500 bg-ember-500/10 text-white" : "border-ink-600 bg-ink-900 text-stone-400 hover:border-ember-500/40"
            }`}>
            Upload musik saya
          </button>
        </div>
        {musicMode === "upload" && (
          <AudioUploadZone state={audioUpload} onFile={handleAudioFile}
            onClear={() => setAudioUpload(EMPTY_AUDIO)} disabled={busy} />
        )}
        {shown("music") && <p className="mt-1 text-xs text-red-400">{shown("music")}</p>}
      </div>
    </>
  );
}
