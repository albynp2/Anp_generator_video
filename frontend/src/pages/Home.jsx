import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Clapperboard, Film, Flame, LayoutTemplate, Music2, Sparkles } from "lucide-react";
import UploadZone from "../components/UploadZone.jsx";
import Field from "../components/Field.jsx";
import TimeInput from "../components/TimeInput.jsx";
import FitToggle from "../components/FitToggle.jsx";
import PreviewPanel from "../components/PreviewPanel.jsx";
import CaptionPanel from "../components/CaptionPanel.jsx";
import MuteMusicFields from "../components/MuteMusicFields.jsx";
import Toggle from "../components/Toggle.jsx";
import MuteRangesEditor from "../components/MuteRangesEditor.jsx";
import AudioUploadZone from "../components/AudioUploadZone.jsx";
import { deleteUpload, generateClip, getHealth, getStatus, getTemplates, uploadAudio, uploadVideo } from "../services/api.js";
import { parseTimecode } from "../utils/time.js";

const EMPTY_UPLOAD = { status: "idle", progress: 0, info: null, error: "", fileName: "" };
const EMPTY_AUDIO = { status: "idle", progress: 0, info: null, error: "" };
const INITIAL_FORM = { episode: "", start: "", end: "", title: "", template: "default", fit: "cover", videoLayout: "template_background", outputPreset: "1080x1920", outputWidth: 1080, outputHeight: 1920, arc: "", notes: "", caption: true };
const TITLE_LIMIT = 200;
const PREF_KEY = "anp-clipper.caption.prefs";
const LEGACY_PREF_KEY = "hersclipp.caption.prefs";

function loadPrefs() {
  try {
    const current = localStorage.getItem(PREF_KEY);
    const legacy = current ? null : localStorage.getItem(LEGACY_PREF_KEY);
    if (!current && legacy) localStorage.setItem(PREF_KEY, legacy);
    return JSON.parse(current || legacy || "null");
  } catch {
    return null;
  }
}
function savePrefs(p) {
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify(p));
  } catch {
    /* storage diblokir: abaikan */
  }
}

export default function Home({ onOpenBuilder }) {
  const [upload, setUpload] = useState(EMPTY_UPLOAD);
  const [sourcePreviewUrl, setSourcePreviewUrl] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [templates, setTemplates] = useState([]);
  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState("");
  const [systemWarning, setSystemWarning] = useState("");
  const [touched, setTouched] = useState(false);
  const [retention, setRetention] = useState(0);
  const [captionAi, setCaptionAi] = useState(true);
  const [saver, setSaver] = useState(false); // mode hemat token: frame lebih sedikit
  const [replaceAudio, setReplaceAudio] = useState(false);
  const [musicMode, setMusicMode] = useState("default"); // "default" | "upload"
  const [audioUpload, setAudioUpload] = useState(EMPTY_AUDIO);
  const [muteRows, setMuteRows] = useState([]);
  const [defaultMusicAvailable, setDefaultMusicAvailable] = useState(true);
  const [mode, setMode] = useState("clip"); // "clip" | "audio_only"
  const pollRef = useRef(null);

  const busy = submitting || job?.status === "queued" || job?.status === "processing";
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  // --- template dinamis + health check
  useEffect(() => {
    let mounted = true;
    const refreshTemplates = async (showError = false) => {
      try {
        const d = await getTemplates();
        if (!mounted) return;
        const next = Array.isArray(d.templates) ? d.templates : [];
        setTemplates(next);
        setForm((f) => {
          // Pertahankan pilihan aktif jika masih tersedia. Jika template dihapus,
          // pindah ke default/pertama yang masih ada; jika kosong, kosongkan pilihan.
          if (next.some((t) => t.name === f.template)) return f;
          const fallback = next.find((t) => t.name === "default") || next[0];
          return { ...f, template: fallback?.name || "" };
        });
      } catch (e) {
        if (mounted && showError) setSystemWarning(e.message);
      }
    };

    refreshTemplates(true);
    // Perubahan file PNG/JSON pada bind mount akan tercermin tanpa reload halaman.
    const timer = setInterval(() => refreshTemplates(false), 15000);
    const onFocus = () => refreshTemplates(false);
    window.addEventListener("focus", onFocus);

    getHealth()
      .then((h) => {
        setRetention(h.retention_minutes || 0);
        setCaptionAi(!!h.caption_ai);
        setDefaultMusicAvailable(!!h.default_music_available);
        const saved = loadPrefs();
        if (saved) {
          setForm((f) => ({ ...f, caption: !!saved.caption }));
          setSaver(!!saved.saver);
        } else {
          setForm((f) => ({ ...f, caption: h.caption_default_on !== false }));
        }
        if (!h.ffmpeg) setSystemWarning("FFmpeg belum terpasang di server — rendering tidak akan berjalan.");
        else if (h.missing_fonts?.length)
          setSystemWarning(
            `Font ${h.missing_fonts.join(", ")} belum terpasang di assets/fonts — memakai font cadangan, gaya teks belum persis referensi. Lihat README (bagian Font).`
          );
      })
      .catch(() => {});

    return () => {
      mounted = false;
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  // --- polling status job
  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const startPolling = useCallback(
    (jobId) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const s = await getStatus(jobId);
          setJob(s);
          if (s.status === "completed" || s.status === "failed") {
            stopPolling();
            if (s.status === "failed") setApiError(s.error || "Rendering gagal.");
          }
        } catch (e) {
          stopPolling();
          setApiError(e.message);
          setJob((j) => (j ? { ...j, status: "failed" } : j));
        }
      }, 1000);
    },
    [stopPolling]
  );

  useEffect(() => () => { if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl); }, [sourcePreviewUrl]);

  // --- upload
  const handleFile = async (file) => {
    setSourcePreviewUrl(URL.createObjectURL(file));
    setApiError("");
    setJob(null);
    setUpload({ ...EMPTY_UPLOAD, status: "uploading", fileName: file.name });
    try {
      const info = await uploadVideo(file, (p) => setUpload((u) => ({ ...u, progress: p })));
      setUpload({ status: "done", progress: 100, info, error: "", fileName: file.name });
    } catch (e) {
      setUpload({ ...EMPTY_UPLOAD, status: "error", error: e.message });
    }
  };


  const handleAudioFile = async (file) => {
    setAudioUpload({ ...EMPTY_AUDIO, status: "uploading" });
    try {
      const info = await uploadAudio(file, (p) => setAudioUpload((a) => ({ ...a, progress: p })));
      setAudioUpload({ status: "done", progress: 100, info, error: "" });
    } catch (e) {
      setAudioUpload({ ...EMPTY_AUDIO, status: "error", error: e.message });
    }
  };

  // --- validasi sisi client (backend tetap validasi ulang)
  const errors = useMemo(() => {
    const e = {};
    if (mode === "clip") {
      if (!form.episode.trim()) e.episode = "Teks utama wajib diisi.";
      else if (form.episode.trim().length > 120) e.episode = "Teks utama maksimal 120 karakter.";
      const s = parseTimecode(form.start);
      const en = parseTimecode(form.end);
      const dur = upload.info?.duration;
      if (!form.start.trim()) e.start = "Start wajib diisi.";
      else if (s === null) e.start = "Format HH:MM:SS, contoh 00:03:25.";
      if (!form.end.trim()) e.end = "End wajib diisi.";
      else if (en === null) e.end = "Format HH:MM:SS, contoh 00:04:18.";
      else if (s !== null && en <= s) e.end = "End time harus lebih besar dari Start time.";
      else if (dur && en > dur + 0.001) e.end = "End time tidak boleh melebihi durasi video.";
      if (!form.title.trim()) e.title = "Title wajib diisi.";
    }
    const wantsReplace = mode === "audio_only" || replaceAudio;
    if (wantsReplace) {
      const filled = muteRows.filter((r) => r.start.trim() || r.end.trim());
      if (!filled.length) e.muteRanges = "Isi minimal satu rentang waktu.";
      else {
        for (const r of filled) {
          const rs = parseTimecode(r.start);
          const rend = parseTimecode(r.end);
          if (rs === null || rend === null) { e.muteRanges = "Format waktu rentang tidak valid."; break; }
          if (rend <= rs) { e.muteRanges = "End rentang harus lebih besar dari Start."; break; }
        }
      }
      if (musicMode === "upload" && audioUpload.status !== "done") e.music = "Upload musik pengganti dulu, atau pilih Musik default.";
      if (musicMode === "default" && !defaultMusicAvailable) e.music = "Musik default belum tersedia di server. Upload musik sendiri.";
    }
    return e;
  }, [form, upload.info, replaceAudio, muteRows, musicMode, audioUpload, defaultMusicAvailable, mode]);

  const canSubmit = upload.status === "done" && !busy && (mode !== "clip" || templates.length > 0);

  const handleGenerate = async () => {
    setTouched(true);
    setApiError("");
    if (Object.keys(errors).length) return;
    setApiError("");
    setSubmitting(true);
    setJob(null);
    try {
      const wantsReplace = mode === "audio_only" || replaceAudio;
      const payload = {
        upload_id: upload.info.upload_id,
        template: form.template,
        fit: form.fit,
        video_layout: "template_background",
        output_width: Number(form.outputWidth),
        output_height: Number(form.outputHeight),
        audio_only: mode === "audio_only",
        caption: mode === "clip" ? form.caption : false,
        replace_audio: wantsReplace,
        music_upload_id: wantsReplace && musicMode === "upload" ? audioUpload.info?.upload_id || "" : "",
        use_default_music: wantsReplace && musicMode === "default",
        mute_ranges: wantsReplace ? muteRows.map((r) => ({ start: r.start, end: r.end })) : [],
      };
      if (mode === "clip") {
        Object.assign(payload, {
          episode: form.episode.trim(),
          start: form.start.trim(),
          end: form.end.trim(),
          title: form.title.trim(),
          arc: form.arc.trim(),
          notes: form.notes.trim(),
          frames: form.caption && saver ? 3 : 0,
        });
      }
      const res = await generateClip(payload);
      setJob({ job_id: res.job_id, status: res.status, progress: 0, stage: "Menunggu antrean" });
      startPolling(res.job_id);
    } catch (e) {
      setApiError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const shown = (key) => (touched ? errors[key] : undefined);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-6 flex items-center gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-ember-600 to-gold-500 shadow-glow">
          <Flame className="h-6 w-6 text-ink-950" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-3xl leading-none tracking-wide">
            <span className="bg-gradient-to-r from-ember-400 to-gold-300 bg-clip-text text-transparent">ANP VIDEO GENERATOR</span>
          </h1>
          <p className="text-xs text-stone-500">
            {mode === "audio_only"
              ? "Ganti audio video yang sudah jadi — tanpa potong atau template"
              : "Engine video untuk teks overlay dan caption · siap Reels & TikTok"}
          </p>
        </div>
        <button className="btn-ghost shrink-0" onClick={onOpenBuilder} title="Buat template baru tanpa edit JSON">
          <LayoutTemplate className="h-4 w-4" /> <span className="hidden sm:inline">Template Builder</span>
        </button>
      </header>

      {systemWarning && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {systemWarning}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
        {/* KIRI: form */}
        <section className="panel space-y-5 p-4 sm:p-6">
          <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-gold-400">
            <Clapperboard className="h-4 w-4" /> Pengaturan Video
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button type="button" disabled={busy}
              onClick={() => { setMode("clip"); setJob(null); }}
              className={`rounded-xl border px-3 py-3 text-left transition disabled:opacity-50 ${
                mode === "clip" ? "border-ember-500 bg-ember-500/10" : "border-ink-600 bg-ink-900 hover:border-ember-500/40"
              }`}>
              <span className="flex items-center gap-2 text-sm font-bold text-stone-100"><Film className="h-4 w-4 text-ember-400" /> Buat Video dengan Teks</span>
              <span className="mt-1 block text-[11px] text-stone-500">Dari template, potong video, tambahkan teks &amp; judul</span>
            </button>
            <button type="button" disabled={busy}
              onClick={() => { setMode("audio_only"); setJob(null); }}
              className={`rounded-xl border px-3 py-3 text-left transition disabled:opacity-50 ${
                mode === "audio_only" ? "border-ember-500 bg-ember-500/10" : "border-ink-600 bg-ink-900 hover:border-ember-500/40"
              }`}>
              <span className="flex items-center gap-2 text-sm font-bold text-stone-100"><Music2 className="h-4 w-4 text-ember-400" /> Ganti Audio Saja</span>
              <span className="mt-1 block text-[11px] text-stone-500">Video yang sudah jadi — hanya mengganti audio</span>
            </button>
          </div>

          <Field label="Video">
            <UploadZone state={upload} onFile={handleFile} onClear={() => {
              if (upload.info) deleteUpload(upload.info.upload_id).catch(() => {});
              setUpload(EMPTY_UPLOAD);
              setSourcePreviewUrl("");
              setJob(null);
            }} disabled={busy} />
          </Field>

          {mode === "clip" && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Teks utama" error={shown("episode")} hint="Teks yang ditampilkan pada area teks template">
                  <input className={`input ${shown("episode") ? "input-error" : ""}`} placeholder="Contoh: Fakta Menarik"
                    value={form.episode} onChange={(e) => set("episode")(e.target.value)} disabled={busy} maxLength={120} />
                </Field>
                <Field label="Start" error={shown("start")}>
                  <TimeInput value={form.start} onChange={set("start")} invalid={!!shown("start")} disabled={busy} />
                </Field>
                <Field label="End" error={shown("end")}>
                  <TimeInput value={form.end} onChange={set("end")} invalid={!!shown("end")} disabled={busy} />
                </Field>
              </div>

              <Field label="Title" error={shown("title")} hint={`${form.title.length}/${TITLE_LIMIT} — otomatis di-wrap & di-center`}>
                <textarea className={`input min-h-[92px] resize-y ${shown("title") ? "input-error" : ""}`} rows={3}
                  placeholder="Teks judul untuk video ini"
                  value={form.title} maxLength={TITLE_LIMIT} onChange={(e) => set("title")(e.target.value)} disabled={busy} />
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Template">
                  <select className="input" value={form.template} onChange={(e) => set("template")(e.target.value)} disabled={busy || templates.length === 0}>
                    {templates.length === 0 && <option value="">Tidak ada template tersedia</option>}
                    {templates.map((t) => (
                      <option key={t.name} value={t.name}>{t.label}</option>
                    ))}
                  </select>
                  {templates.length === 0 && (
                    <p className="mt-1 text-xs text-amber-300">Semua template sedang dihapus/nonaktif. Tambahkan PNG dan JSON template untuk mengaktifkan Generate Video.</p>
                  )}
                </Field>
                <Field label="Video Fit">
                  <FitToggle value={form.fit} onChange={set("fit")} disabled={busy} />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Resolusi Output" hint="Default Full HD 9:16 untuk Facebook, Instagram, YouTube Shorts, dan TikTok.">
                  <select className="input" value={form.outputPreset} disabled={busy}
                    onChange={(e) => {
                      const value = e.target.value;
                      const presets = {
                        "1080x1920": [1080, 1920], "720x1280": [720, 1280],
                        "1920x1080": [1920, 1080], "1280x720": [1280, 720],
                        "1080x1080": [1080, 1080]
                      };
                      const dims = presets[value];
                      setForm((f) => ({ ...f, outputPreset: value,
                        ...(dims ? { outputWidth: dims[0], outputHeight: dims[1] } : {}) }));
                    }}>
                    <option value="1080x1920">Full HD Portrait — 1080 × 1920 (9:16)</option>
                    <option value="720x1280">HD Portrait — 720 × 1280 (9:16)</option>
                    <option value="1920x1080">Full HD Landscape — 1920 × 1080 (16:9)</option>
                    <option value="1280x720">HD Landscape — 1280 × 720 (16:9)</option>
                    <option value="1080x1080">Square — 1080 × 1080 (1:1)</option>
                    <option value="custom">Custom</option>
                  </select>
                </Field>
                {form.outputPreset === "custom" ? (
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Width (px)">
                      <input className="input" type="number" min="256" max="4096" step="2" value={form.outputWidth}
                        disabled={busy} onChange={(e) => set("outputWidth")(e.target.value)} />
                    </Field>
                    <Field label="Height (px)">
                      <input className="input" type="number" min="256" max="4096" step="2" value={form.outputHeight}
                        disabled={busy} onChange={(e) => set("outputHeight")(e.target.value)} />
                    </Field>
                  </div>
                ) : (
                  <div className="flex items-end pb-2 text-xs text-stone-500">Output: {form.outputWidth} × {form.outputHeight} px</div>
                )}
              </div>

              <div className="space-y-4 rounded-xl border border-ink-600/70 bg-ink-900/60 p-3">
                <Toggle
                  checked={form.caption}
                  disabled={busy}
                  label="Buat caption otomatis"
                  hint={
                    form.caption
                      ? captionAi
                        ? "Memanggil API AI setelah video jadi (memakai token)."
                        : "API key belum diisi: hanya caption dasar (judul + hashtag), tanpa token."
                      : "Tanpa caption. Tidak ada panggilan API, jadi tidak memakai token."
                  }
                  onChange={(v) => {
                    set("caption")(v);
                    savePrefs({ caption: v, saver });
                  }}
                />
                {form.caption && (
                  <>
                    <Field label="Kategori / konteks (opsional)" hint="Jadi baris pertama caption, mis. Tutorial, Edukasi, Review">
                      <input className="input" placeholder="Tutorial" value={form.arc} maxLength={60}
                        onChange={(e) => set("arc")(e.target.value)} disabled={busy} />
                    </Field>
                    <Field label="Catatan cerita (opsional)" hint="Makin jelas catatan, makin akurat caption: siapa, di mana, apa yang terjadi.">
                      <textarea className="input min-h-[72px] resize-y" rows={3} maxLength={1200}
                        placeholder="Contoh: Jelaskan adegan, konteks, atau pesan utama video…"
                        value={form.notes} onChange={(e) => set("notes")(e.target.value)} disabled={busy} />
                    </Field>
                    <Toggle
                      checked={saver}
                      disabled={busy}
                      label="Mode hemat token"
                      hint={saver ? "3 frame dikirim ke AI (lebih murah, alur bisa kurang lengkap)." : "6 frame dikirim ke AI (lebih akurat)."}
                      onChange={(v) => {
                        setSaver(v);
                        savePrefs({ caption: form.caption, saver: v });
                      }}
                    />
                  </>
                )}
              </div>

              <div className="space-y-4 rounded-xl border border-ink-600/70 bg-ink-900/60 p-3">
                <Toggle
                  checked={replaceAudio}
                  disabled={busy}
                  label="Ganti Audio (hak cipta)"
                  hint={
                    replaceAudio
                      ? "Audio asli disenyapkan pada rentang yang diisi, lalu ditimpa musik pengganti."
                      : "Audio clip memakai suara asli video sepenuhnya."
                  }
                  onChange={setReplaceAudio}
                />
                {replaceAudio && (
                  <MuteMusicFields
                    muteRows={muteRows} setMuteRows={setMuteRows} busy={busy} shown={shown}
                    musicMode={musicMode} setMusicMode={setMusicMode} defaultMusicAvailable={defaultMusicAvailable}
                    audioUpload={audioUpload} handleAudioFile={handleAudioFile} setAudioUpload={setAudioUpload} EMPTY_AUDIO={EMPTY_AUDIO}
                  />
                )}
              </div>
            </>
          )}

          {mode === "audio_only" && (
            <div className="space-y-4 rounded-xl border border-ink-600/70 bg-ink-900/60 p-3">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-100">
                <Music2 className="h-4 w-4 text-ember-400" /> Ganti Audio
              </p>
              <p className="-mt-2 text-xs text-stone-500">
                Video dipakai penuh apa adanya (tanpa potong, tanpa template, tanpa caption) — cuma bagian audio di rentang
                di bawah ini yang disenyapkan lalu ditimpa musik pengganti.
              </p>
              <MuteMusicFields
                muteRows={muteRows} setMuteRows={setMuteRows} busy={busy} shown={shown}
                musicMode={musicMode} setMusicMode={setMusicMode} defaultMusicAvailable={defaultMusicAvailable}
                audioUpload={audioUpload} handleAudioFile={handleAudioFile} setAudioUpload={setAudioUpload} EMPTY_AUDIO={EMPTY_AUDIO}
              />
            </div>
          )}

          {apiError && (
            <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{apiError}</span>
            </div>
          )}

          <button className="btn-primary w-full" onClick={handleGenerate} disabled={!canSubmit}>
            <Sparkles className="h-4 w-4" />
            {busy ? "Sedang memproses…" : mode === "audio_only" ? "Ganti Audio" : "Generate Video"}
          </button>
          {upload.status !== "done" && (
            <p className="-mt-2 text-center text-xs text-stone-500">Upload video terlebih dahulu.</p>
          )}
        </section>

        {/* KANAN: preview */}
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <PreviewPanel job={job} template={mode === "clip" ? form.template : null} sourcePreviewUrl={mode === "clip" ? sourcePreviewUrl : ""} fit={form.fit} videoArea={templates.find((t) => t.name === form.template)?.video_area} templateWidth={templates.find((t) => t.name === form.template)?.width} templateHeight={templates.find((t) => t.name === form.template)?.height} startSeconds={parseTimecode(form.start) ?? 0} endSeconds={parseTimecode(form.end)} retentionMinutes={retention} outputWidth={form.outputWidth} outputHeight={form.outputHeight} onDeleted={() => { stopPolling(); setJob(null); }} />
          {job?.status === "completed" && job.caption_status !== "off" && (
            <CaptionPanel jobId={job.job_id} arc={form.arc.trim()} notes={form.notes.trim()} />
          )}
        </aside>
      </div>
    </div>
  );
}
