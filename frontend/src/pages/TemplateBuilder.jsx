import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, Check, Download, Flame, Loader2, MousePointerSquareDashed, Save, UploadCloud } from "lucide-react";
import { saveTemplate, previewTemplate } from "../services/api.js";

const AREA_DEFS = [
  { key: "video", label: "Video Area", color: "#ff6a00", desc: "Area untuk menempatkan video" },
  { key: "episode", label: "Text Area", color: "#22c55e", desc: "Area teks utama / caption" },
  { key: "title", label: "Title Area", color: "#3b82f6", desc: "Area judul video" },
];
const FONT_THEMES = {
  cinematic: { label: "Cinematic", font: "Almendra-Bold.ttf", fallback: ["Sansita-ExtraBoldItalic.ttf", "Lora-Italic-Variable.ttf"] },
  bold: { label: "Bold Impact", font: "Sansita-ExtraBold.ttf", fallback: ["Amaranth-BoldItalic.ttf"] },
  modern: { label: "Modern", font: "AlegreyaSans-ExtraBoldItalic.ttf", fallback: ["Sansita-ExtraBold.ttf"] },
  elegant: { label: "Elegant", font: "Lora-Italic-Variable.ttf", fallback: ["Almendra-Bold.ttf"] },
  playful: { label: "Playful", font: "Amaranth-BoldItalic.ttf", fallback: ["Sansita-BoldItalic.ttf"] },
};
const STYLE_TYPES = [
  ["plain", "Normal"], ["bold", "Bold"], ["outline", "Outline"],
  ["shadow", "Shadow / bayangan"], ["glow", "Glow / bercahaya"], ["fire", "Fire / api"],
];
const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
function autoAreasFor(w, h) {
  // Layout generik: video di tengah, teks utama di atas, judul di bawah.
  const vertical = h >= w;
  const video = vertical
    ? { x: 0, y: Math.round(h * .15), width: w, height: Math.round(h * .70) }
    : { x: Math.round(w * .15), y: 0, width: Math.round(w * .70), height: h };
  const episode = vertical
    ? { x: Math.round(w * .05), y: Math.round(h * .015), width: Math.round(w * .90), height: Math.round(h * .12) }
    : { x: Math.round(w * .05), y: Math.round(h * .05), width: Math.round(w * .90), height: Math.round(h * .12) };
  const title = vertical
    ? { x: Math.round(w * .05), y: Math.round(h * .865), width: Math.round(w * .90), height: Math.round(h * .12) }
    : { x: Math.round(w * .05), y: Math.round(h * .83), width: Math.round(w * .90), height: Math.round(h * .12) };
  return { video, episode, title };
}

export default function TemplateBuilder({ onBack }) {
  const canvasRef = useRef(null), fileRef = useRef(null), imgRef = useRef(null), previewImageRef = useRef(null), previewUrlRef = useRef(null), fileObjRef = useRef(null);
  const scaleRef = useRef(1), dragRef = useRef(null);
  const [natSize, setNatSize] = useState(null);
  const [mode, setMode] = useState("auto");
  const [areas, setAreas] = useState({ video: null, episode: null, title: null });
  const [active, setActive] = useState("video");
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [epFormat, setEpFormat] = useState("");
  const [epSize, setEpSize] = useState(20), [tiSize, setTiSize] = useState(20);
  const [fontTheme, setFontTheme] = useState("cinematic"), [textType, setTextType] = useState("shadow");
  const [textColor, setTextColor] = useState("#ffffff"), [strokeColor, setStrokeColor] = useState("#171717");
  const [strokeWidth, setStrokeWidth] = useState(2), [shadowBlur, setShadowBlur] = useState(0);
  const [showTextBackground, setShowTextBackground] = useState(true), [backgroundColor, setBackgroundColor] = useState("#333333");
  const [backgroundOpacity, setBackgroundOpacity] = useState(10), [backgroundPadding, setBackgroundPadding] = useState(0), [backgroundRadius, setBackgroundRadius] = useState(0);
  const [hint, setHint] = useState(""), [jsonOut, setJsonOut] = useState(""), [saving, setSaving] = useState(false), [saveMsg, setSaveMsg] = useState(null), [previewError, setPreviewError] = useState("");

  const currentAreas = natSize ? (mode === "auto" ? autoAreasFor(natSize.w, natSize.h) : areas) : areas;
  const draw = () => {
    const cv = canvasRef.current; if (!cv) return;
    const ctx = cv.getContext("2d"); ctx.clearRect(0, 0, cv.width, cv.height);
    const baseImage = previewImageRef.current || imgRef.current;
    if (baseImage) ctx.drawImage(baseImage, 0, 0, cv.width, cv.height);
    if (!natSize) return;
    const s = scaleRef.current;
    const drawLabel = (text, area, size, color, bg = false) => {
      if (!area) return;
      const x = area.x * s, y = area.y * s, w = area.width * s, h = area.height * s;
      ctx.save(); ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const px = clamp(Number(size) * s, 10, 64); ctx.font = `${textType === "bold" ? "900" : "italic 800"} ${px}px ${({cinematic:"ThemeCinematic",bold:"ThemeBold",modern:"ThemeModern",elegant:"ThemeElegant",playful:"ThemePlayful"})[fontTheme] || "ThemeCinematic"}`;
      const sample = text || "Preview teks";
      const maxW = Math.max(20, w - 14 * s);
      let shown = sample;
      while (ctx.measureText(shown).width > maxW && shown.length > 4) shown = shown.slice(0, -2) + "…";
      const tw = Math.min(maxW, ctx.measureText(shown).width + Number(backgroundPadding) * s * 2);
      const th = Math.min(h - 2, px * 1.55 + Number(backgroundPadding) * s * 2);
      if (bg && showTextBackground) {
        ctx.globalAlpha = Number(backgroundOpacity) / 100; ctx.fillStyle = backgroundColor;
        ctx.beginPath(); ctx.roundRect(x + (w - tw) / 2, y + (h - th) / 2, tw, th, Number(backgroundRadius) * s); ctx.fill();
      }
      ctx.globalAlpha = 1; ctx.fillStyle = color; ctx.shadowColor = textType === "glow" ? color : "#000";
      ctx.shadowBlur = ["shadow", "glow"].includes(textType) ? Number(shadowBlur) * s : 0;
      if (textType === "outline") { ctx.lineWidth = Math.max(1, Number(strokeWidth) * s); ctx.strokeStyle = strokeColor; ctx.strokeText(shown, x + w / 2, y + h / 2, maxW); }
      ctx.fillText(shown, x + w / 2, y + h / 2, maxW); ctx.restore();
    };
    drawLabel("Contoh teks utama", currentAreas.episode, epSize, textColor, true);
    drawLabel("Judul video", currentAreas.title, tiSize, textColor, true);
    if (mode === "manual") for (const { key, color, label: areaLabel } of AREA_DEFS) {
      const a = currentAreas[key]; if (!a) continue;
      ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = key === active && mode === "manual" ? 3 : 2;
      ctx.setLineDash(key === active && mode === "manual" ? [] : [6, 4]);
      ctx.strokeRect(a.x * s, a.y * s, a.width * s, a.height * s);
      ctx.fillStyle = `${color}20`; ctx.fillRect(a.x * s, a.y * s, a.width * s, a.height * s);
      ctx.fillStyle = color; ctx.font = `bold ${Math.max(10, 12 * s)}px Arial`; ctx.fillText(areaLabel, a.x * s + 5, a.y * s + 13);
      ctx.restore();
    }
  };
  useEffect(() => {
    if (!natSize || !fileObjRef.current) { draw(); return; }
    let cancelled = false;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const { config } = buildConfig();
        const url = await previewTemplate(config, fileObjRef.current, "Contoh teks utama", "Judul video", controller.signal);
        if (cancelled) { URL.revokeObjectURL(url); return; }
        const image = new Image();
        image.onload = () => {
          if (cancelled) { URL.revokeObjectURL(url); return; }
          if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
          previewUrlRef.current = url;
          previewImageRef.current = image;
          setPreviewError("");
          draw();
        };
        image.onerror = () => { URL.revokeObjectURL(url); if (!cancelled) setPreviewError("Gagal memuat preview hasil renderer."); };
        image.src = url;
      } catch (err) {
        if (!cancelled && err.name !== "AbortError") setPreviewError(err.message || "Preview backend gagal.");
      }
    }, 280);
    return () => { cancelled = true; clearTimeout(timer); controller.abort(); };
  }, [areas, active, natSize, mode, epSize, tiSize, fontTheme, textType, textColor, strokeColor, strokeWidth, shadowBlur, showTextBackground, backgroundColor, backgroundOpacity, backgroundPadding, backgroundRadius]);

  const handleFile = (file) => {
    if (!file) return;
    fileObjRef.current = file; setSaveMsg(null);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const image = new Image();
      image.onload = () => {
        imgRef.current = image; previewImageRef.current = null; if (previewUrlRef.current) { URL.revokeObjectURL(previewUrlRef.current); previewUrlRef.current = null; } const w = image.naturalWidth, h = image.naturalHeight;
        const s = Math.min(640 / w, 860 / h, 1); scaleRef.current = s;
        const cv = canvasRef.current; cv.width = Math.max(1, Math.round(w * s)); cv.height = Math.max(1, Math.round(h * s));
        setNatSize({ w, h }); setAreas(autoAreasFor(w, h)); setMode("auto"); setJsonOut(""); setHint("");
        requestAnimationFrame(draw);
      }; image.src = ev.target.result;
    }; reader.readAsDataURL(file);
  };
  const toXY = (evt) => { const cv = canvasRef.current, r = cv.getBoundingClientRect(), p = evt.touches ? evt.touches[0] : evt; return [clamp((p.clientX-r.left)*(cv.width/r.width),0,cv.width), clamp((p.clientY-r.top)*(cv.height/r.height),0,cv.height)]; };
  const normRect = (x0,y0,x1,y1) => {
    const s=scaleRef.current, cw=natSize?.w-(natSize?.w%2), ch=natSize?.h-(natSize?.h%2);
    const left=Math.min(x0,x1), top=Math.min(y0,y1);
    const x=clamp(Math.round(left/s),0,Math.max(0,cw-2)), y=clamp(Math.round(top/s),0,Math.max(0,ch-2));
    const right=clamp(Math.round(Math.max(x0,x1)/s),x+2,cw), bottom=clamp(Math.round(Math.max(y0,y1)/s),y+2,ch);
    return {x,y,width:right-x,height:bottom-y};
  };
  const onDown = (e) => { if (!imgRef.current || mode !== "manual") return; e.preventDefault(); dragRef.current = toXY(e); };
  const onMove = (e) => { if (!dragRef.current || mode !== "manual") return; e.preventDefault(); const [x,y]=toXY(e); setAreas(a=>({...a,[active]:normRect(dragRef.current[0],dragRef.current[1],x,y)})); };
  const onUp = () => { dragRef.current=null; };
  const canGenerate = !!(natSize && currentAreas.video && currentAreas.episode && currentAreas.title && name.trim());
  const buildConfig = () => {
    const slug = name.trim().toLowerCase().replace(/[^a-z0-9_-]/g,"-");
    // Canvas H.264 harus genap. Hitung Auto Area dari dimensi canvas final,
    // bukan ukuran gambar mentah, agar tidak overflow saat gambar berukuran ganjil.
    const w=natSize.w-(natSize.w%2), h=natSize.h-(natSize.h%2), font=FONT_THEMES[fontTheme];
    const sourceAreas = mode === "auto" ? autoAreasFor(w, h) : areas;
    const fitArea = (a) => {
      if (!a) return a;
      const x=clamp(Math.round(a.x),0,w-2), y=clamp(Math.round(a.y),0,h-2);
      return {x,y,width:clamp(Math.round(a.width),2,w-x),height:clamp(Math.round(a.height),2,h-y)};
    };
    const safeAreas = { video:fitArea(sourceAreas.video), episode:fitArea(sourceAreas.episode), title:fitArea(sourceAreas.title) };
    const common = {
      font: font.font, font_fallbacks: font.fallback, style_type: textType, color: textColor, stroke_color: strokeColor,
      stroke_width: textType === "outline" ? Number(strokeWidth) : 0,
      shadow: ["shadow","glow"].includes(textType) ? { offset:[2,3], blur:Number(shadowBlur), color:textType === "glow" ? textColor : "#000000", opacity:0.75 } : null,
      background: { enabled: showTextBackground, color: backgroundColor, opacity:Number(backgroundOpacity)/100, padding:Number(backgroundPadding), radius:Number(backgroundRadius) },
      fire: { enabled:textType === "fire", spread:30, lift:8, sparks:30, brightness:0.68 },
    };
    return { slug, config:{ name:slug, label:label.trim() || slug, image:`${slug}.png`, canvas:{width:w,height:h}, layout_mode:mode,
      video_area:safeAreas.video, episode_area:safeAreas.episode, title_area:safeAreas.title,
      episode:{...common,text_format:epFormat.trim() || "{text}",font_size:Number(epSize)||56,min_font_size:Math.max(12,Math.round((Number(epSize)||56)*.6))},
      title:{...common,font_size:Number(tiSize)||62,min_font_size:Math.max(12,Math.round((Number(tiSize)||62)*.65)),max_lines:3,max_width:Math.round(safeAreas.title.width*.95),line_spacing:1.18}
    }};
  };
  const downloadOnly = () => { if(!canGenerate){setHint("Pilih gambar template dan isi nama file terlebih dahulu.");return;} const {slug,config}=buildConfig(); const json=JSON.stringify(config,null,2);setJsonOut(json);const url=URL.createObjectURL(new Blob([json],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download=`${slug}.json`;a.click();URL.revokeObjectURL(url);setHint(`File ${slug}.json berhasil disiapkan.`); };
  const saveToServer = async (overwrite=false) => {
    if(!canGenerate){setHint("Pilih gambar template dan isi nama file terlebih dahulu.");return;}
    if(!fileObjRef.current){setSaveMsg({type:"error",text:"Gambar asli tidak ditemukan. Pilih ulang gambar template."});return;}
    const {slug,config}=buildConfig();setJsonOut(JSON.stringify(config,null,2));setSaving(true);setSaveMsg(null);
    try{await saveTemplate(config,fileObjRef.current,overwrite);setSaveMsg({type:"ok",text:`Template ${slug} berhasil disimpan dan siap dipilih di dashboard.`});}
    catch(e){if(e.code==="template_exists")setSaveMsg({type:"conflict",text:e.message,slug});else setSaveMsg({type:"error",text:e.message});}
    finally{setSaving(false);}
  };

  return <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
    <header className="mb-6 flex items-center gap-3"><button className="btn-ghost !px-3 !py-2.5" onClick={onBack}><ArrowLeft className="h-4 w-4"/>Kembali</button><div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-ember-600 to-gold-500 shadow-glow"><MousePointerSquareDashed className="h-6 w-6 text-ink-950"/></div><div><h1 className="font-display text-2xl leading-none tracking-wide"><span className="bg-gradient-to-r from-ember-400 to-gold-300 bg-clip-text text-transparent">Template Builder</span></h1><p className="text-xs text-stone-500">Atur area, font, dan gaya teks dengan preview realtime</p></div></header>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <section className="panel space-y-4 p-4 sm:p-6"><div><label className="label">1. Pilih gambar template (PNG/JPG)</label><button className="btn-primary w-full" onClick={()=>fileRef.current?.click()}><UploadCloud className="h-4 w-4"/>Pilih Gambar</button><input ref={fileRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={e=>handleFile(e.target.files?.[0])}/></div>
        <div className="flex justify-center overflow-auto rounded-xl border border-ink-600 bg-ink-950 p-2"><canvas ref={canvasRef} width={640} height={860} className={`max-w-full rounded-lg ${mode === "manual" ? "cursor-crosshair" : "cursor-default"}`} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp} onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}/></div>
        <p className="text-center text-xs text-stone-500">{natSize?`Ukuran gambar asli: ${natSize.w} × ${natSize.h}px. Preview memakai renderer backend yang sama dengan hasil render.`:"Belum ada gambar dimuat."}</p>{previewError&&<p className="text-center text-xs text-red-300">Preview: {previewError}</p>}
      </section>
      <aside className="space-y-5">
        <div className="panel space-y-3 p-4 sm:p-5"><p className="label mb-0">2. Area video & teks</p><label className="label">Mode Template</label><select className="input" value={mode} onChange={e=>{const next=e.target.value;setMode(next);if(next==="auto"){setFontTheme("cinematic");setTextType("shadow");setEpSize(20);setTiSize(20);setTextColor("#ffffff");setStrokeColor("#171717");setStrokeWidth(2);setShadowBlur(0);setShowTextBackground(true);setBackgroundColor("#333333");setBackgroundOpacity(10);setBackgroundPadding(0);setBackgroundRadius(0);}}}><option value="auto">Auto Template</option><option value="manual">Manual Template</option></select>
          {mode === "auto" ? <p className="text-xs text-stone-400">Posisi Video Area, Text Area, dan Title Area dihitung otomatis dari resolusi gambar. Pengaturan area manual disembunyikan.</p> : <><p className="text-xs text-stone-400">Pilih area, lalu tarik kotak pada gambar untuk mengatur posisi dan ukuran.</p><div className="space-y-2">{AREA_DEFS.map(({key,label:l,color,desc})=><button key={key} onClick={()=>setActive(key)} className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm ${active===key?"border-ember-500 bg-ember-500/10":"border-ink-600 bg-ink-900"}`}><span className="h-3 w-3 rounded-sm" style={{background:color}}/><span className="flex-1"><b className="block text-stone-100">{l}</b><small className="text-stone-500">{currentAreas[key]?`${currentAreas[key].x}, ${currentAreas[key].y} · ${currentAreas[key].width}×${currentAreas[key].height}`:desc}</small></span></button>)}</div></>}
        </div>
        <div className="panel space-y-3 p-4 sm:p-5"><p className="label mb-0">3. Info Template</p><div><label className="label">Nama file (a-z, 0-9, - _)</label><input className="input" value={name} placeholder="nama-template" onChange={e=>setName(e.target.value)}/></div><div><label className="label">Label di dropdown</label><input className="input" value={label} placeholder="Nama template" onChange={e=>setLabel(e.target.value)}/></div><div><label className="label">Format teks utama</label><input className="input" value={epFormat} placeholder="Contoh: {text}" onChange={e=>setEpFormat(e.target.value)}/><p className="text-[11px] text-stone-500">Gunakan {'{text}'} untuk teks yang diinput pada dashboard, atau {'{number}'} jika sumbernya nomor.</p></div></div>
        <div className="panel space-y-3 p-4 sm:p-5"><p className="label mb-0">4. Gaya Teks</p><div><label className="label">Font Theme</label><select className="input" value={fontTheme} onChange={e=>setFontTheme(e.target.value)}>{Object.entries(FONT_THEMES).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></div><div><label className="label">Tipe gaya teks</label><select className="input" value={textType} onChange={e=>setTextType(e.target.value)}>{STYLE_TYPES.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="label">Ukuran teks utama</label><input type="number" min="12" max="300" className="input" value={epSize} onChange={e=>setEpSize(e.target.value)}/></div><div><label className="label">Ukuran title</label><input type="number" min="12" max="300" className="input" value={tiSize} onChange={e=>setTiSize(e.target.value)}/></div><div><label className="label">Warna teks</label><input type="color" className="input h-11 p-1" value={textColor} onChange={e=>setTextColor(e.target.value)}/></div><div><label className="label">Warna outline</label><input type="color" className="input h-11 p-1" value={strokeColor} onChange={e=>setStrokeColor(e.target.value)}/></div><div><label className="label">Ketebalan outline</label><input type="number" min="0" max="12" className="input" value={strokeWidth} onChange={e=>setStrokeWidth(e.target.value)}/></div><div><label className="label">Shadow / glow blur</label><input type="number" min="0" max="40" className="input" value={shadowBlur} onChange={e=>setShadowBlur(e.target.value)}/></div></div>
          <label className="flex items-center gap-2 text-sm text-stone-200"><input type="checkbox" checked={showTextBackground} onChange={e=>setShowTextBackground(e.target.checked)}/> Aktifkan background teks</label><div className="grid grid-cols-2 gap-3"><div><label className="label">Warna background</label><input type="color" className="input h-11 p-1" value={backgroundColor} onChange={e=>setBackgroundColor(e.target.value)}/></div><div><label className="label">Transparansi (%)</label><input type="number" min="0" max="100" className="input" value={backgroundOpacity} onChange={e=>setBackgroundOpacity(e.target.value)}/></div><div><label className="label">Padding background</label><input type="number" min="0" max="100" className="input" value={backgroundPadding} onChange={e=>setBackgroundPadding(e.target.value)}/></div><div><label className="label">Radius sudut</label><input type="number" min="0" max="100" className="input" value={backgroundRadius} onChange={e=>setBackgroundRadius(e.target.value)}/></div></div><p className="text-[11px] text-stone-500">Semua perubahan gaya, ukuran, font, dan background langsung terlihat di preview gambar.</p>
        </div>
        <div className="panel space-y-3 p-4 sm:p-5"><p className="label mb-0">5. Simpan Template</p><button className="btn-primary w-full" onClick={()=>saveToServer(false)} disabled={!canGenerate||saving}>{saving?<Loader2 className="h-4 w-4 animate-spin"/>:<Save className="h-4 w-4"/>}{saving?"Menyimpan…":"Simpan ke Server"}</button><button className="btn-ghost w-full" onClick={downloadOnly} disabled={!canGenerate}><Download className="h-4 w-4"/>Download JSON</button>
          {saveMsg?.type==="ok"&&<div className="flex gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-xs text-emerald-300"><Check className="h-4 w-4"/>{saveMsg.text}</div>}{saveMsg?.type==="error"&&<div className="flex gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-300"><AlertTriangle className="h-4 w-4"/>{saveMsg.text}</div>}{saveMsg?.type==="conflict"&&<div className="space-y-2 text-xs text-amber-200">{saveMsg.text}<button className="btn-ghost w-full" onClick={()=>saveToServer(true)} disabled={saving}>Timpa template {saveMsg.slug}</button></div>}{hint&&<p className="text-xs text-gold-300">{hint}</p>}{jsonOut&&<details><summary className="cursor-pointer text-xs text-stone-400">Lihat JSON</summary><textarea readOnly value={jsonOut} className="input mt-2 min-h-[140px] font-mono text-xs"/></details>}
        </div>
        <div className="panel p-4 text-xs text-stone-400"><p className="mb-2 flex items-center gap-1.5 font-semibold text-gold-400"><Flame className="h-3.5 w-3.5"/>Catatan</p>Template tersimpan dengan gambar resolusi asli. Mode Auto menghitung area berdasarkan rasio gambar; mode Manual menggunakan koordinat yang lu atur sendiri.</div>
      </aside>
    </div>
  </div>;
}
