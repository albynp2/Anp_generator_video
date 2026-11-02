import { useEffect, useState } from "react";
import { ArrowLeft, CopyPlus, Edit3, Loader2, RefreshCw, LayoutTemplate } from "lucide-react";
import { getTemplates, templateImageUrl } from "../services/api.js";

export default function TemplateBuilderEntry({ onBack, onCreate, onEdit }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getTemplates();
      setTemplates((data.templates || []).filter((item) => item.name !== "default"));
    } catch (err) {
      setError(err.message || "Gagal memuat daftar template.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-7 flex items-center gap-3">
        <button className="btn-ghost !px-3 !py-2.5" onClick={onBack}><ArrowLeft className="h-4 w-4" />Kembali</button>
        <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-ember-600 to-gold-500 shadow-glow"><LayoutTemplate className="h-6 w-6 text-ink-950" /></div>
        <div><h1 className="font-display text-2xl leading-none tracking-wide"><span className="bg-gradient-to-r from-ember-400 to-gold-300 bg-clip-text text-transparent">Template Builder</span></h1><p className="text-xs text-stone-500">Buat template baru atau kelola template yang sudah tersedia</p></div>
      </header>

      <div className="grid gap-5 md:grid-cols-2">
        <button onClick={onCreate} className="panel group min-h-56 p-6 text-left transition hover:border-ember-500/70 hover:bg-ember-500/5">
          <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-ember-600 to-gold-500 text-ink-950 shadow-glow"><CopyPlus size={27} /></div>
          <h2 className="mb-2 text-xl font-bold text-stone-100">Buat Template Baru</h2>
          <p className="max-w-md text-sm leading-relaxed text-stone-400">Mulai dari gambar template baru, atur Auto atau Manual, area video, teks, font, dan gaya sesuai kebutuhan.</p>
          <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-gold-300">Mulai membuat <span aria-hidden="true">→</span></span>
        </button>

        <section className="panel min-h-56 p-6">
          <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl border border-violet-400/30 bg-violet-500/10 text-violet-300"><Edit3 size={27} /></div>
          <h2 className="mb-2 text-xl font-bold text-stone-100">Edit Template</h2>
          <p className="text-sm leading-relaxed text-stone-400">Pilih template yang sudah tersimpan untuk membuka konfigurasi dan mengeditnya.</p>
          <div className="mt-5 flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-wider text-stone-500">Template tersedia ({templates.length})</span><button className="btn-ghost !px-2 !py-1.5" onClick={load} disabled={loading} title="Muat ulang daftar"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button></div>
        </section>
      </div>

      <section className="panel mt-5 p-4 sm:p-6">
        <div className="mb-4 flex items-center justify-between"><h3 className="font-semibold text-stone-100">Daftar Template</h3>{loading && <span className="inline-flex items-center gap-2 text-xs text-stone-400"><Loader2 size={14} className="animate-spin" />Memuat...</span>}</div>
        {error && <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}
        {!loading && !error && templates.length === 0 && <div className="rounded-xl border border-dashed border-ink-600 p-8 text-center text-sm text-stone-400">Belum ada template tersimpan. Buat template baru untuk memulai.</div>}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((item) => (
            <button key={item.name} onClick={() => onEdit(item.name)} className="group overflow-hidden rounded-xl border border-ink-600 bg-ink-900 text-left transition hover:border-violet-400/70">
              <div className="flex h-44 items-center justify-center overflow-hidden bg-ink-950"><img src={templateImageUrl(item.name)} alt={item.label} className="h-full w-full object-contain transition group-hover:scale-[1.02]" loading="lazy" /></div>
              <div className="flex items-center justify-between gap-3 p-3"><div className="min-w-0"><p className="truncate font-semibold text-stone-100">{item.label}</p><p className="mt-1 text-xs text-stone-500">{item.width} × {item.height} · {(item.layout_mode || "manual") === "auto" ? "Auto Template" : "Manual Template"}</p></div><Edit3 size={17} className="shrink-0 text-violet-300" /></div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
