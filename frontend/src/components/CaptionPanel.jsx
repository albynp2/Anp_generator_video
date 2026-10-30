import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, Download, Loader2, RefreshCw, ScrollText } from "lucide-react";
import { getCaption, regenerateCaption } from "../services/api.js";

export default function CaptionPanel({ jobId, arc, notes }) {
  const [state, setState] = useState({ loading: true, text: "", source: null, error: null, filename: "caption.txt", fatal: "" });
  const [copied, setCopied] = useState(false);
  const [regen, setRegen] = useState(false);
  const areaRef = useRef(null);

  const apply = (res) =>
    setState({ loading: false, text: res.text, source: res.source, error: res.error, filename: res.filename || "caption.txt", fatal: "" });

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, fatal: "" }));
    getCaption(jobId)
      .then((res) => alive && apply(res))
      .catch((e) => alive && setState((s) => ({ ...s, loading: false, fatal: e.message })));
    return () => {
      alive = false;
    };
  }, [jobId]);

  const copy = useCallback(async () => {
    const text = state.text;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // fallback untuk http:// non-localhost
      areaRef.current?.select();
      document.execCommand("copy");
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }, [state.text]);

  const download = () => {
    const blob = new Blob([state.text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = state.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const regenerate = async () => {
    setRegen(true);
    try {
      apply(await regenerateCaption(jobId, { arc, notes }));
    } catch (e) {
      setState((s) => ({ ...s, error: e.message }));
    } finally {
      setRegen(false);
    }
  };

  return (
    <div className="panel mt-5 p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-gold-400">
        <ScrollText className="h-4 w-4" /> Caption
        {state.source && (
          <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold normal-case tracking-normal ${
            state.source === "ai" ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
          }`}>
            {state.source === "ai" ? "dibuat AI" : "caption dasar"}
          </span>
        )}
      </div>

      {state.loading ? (
        <p className="flex items-center gap-2 text-sm text-stone-400"><Loader2 className="h-4 w-4 animate-spin" /> Memuat caption…</p>
      ) : state.fatal ? (
        <p className="text-sm text-red-300">{state.fatal}</p>
      ) : (
        <>
          {state.error && (
            <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> <span>{state.error}</span>
            </div>
          )}
          <textarea
            ref={areaRef}
            className="input min-h-[280px] resize-y font-mono text-[13px] leading-relaxed"
            value={state.text}
            onChange={(e) => setState((s) => ({ ...s, text: e.target.value }))}
            spellCheck={false}
          />
          <p className="mt-1 text-[11px] text-stone-500">Bisa diedit langsung; Copy &amp; Download memakai teks yang tampil di sini.</p>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <button className="btn-ghost" onClick={copy}>
              {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />} {copied ? "Tercopy" : "Copy"}
            </button>
            <button className="btn-ghost" onClick={download}>
              <Download className="h-4 w-4" /> .txt
            </button>
            <button className="btn-ghost" onClick={regenerate} disabled={regen} title="Buat ulang dengan kategori/konteks dan catatan terbaru di form">
              {regen ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Ulang
            </button>
          </div>
        </>
      )}
    </div>
  );
}
