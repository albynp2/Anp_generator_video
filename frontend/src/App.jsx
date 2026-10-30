import { useEffect, useState } from "react";
import { Clapperboard, Flame, LayoutTemplate, Sparkles } from "lucide-react";
import Home from "./pages/Home.jsx";
import TemplateBuilder from "./pages/TemplateBuilder.jsx";

const ROUTE = "#/template-builder";

export default function App() {
  const [page, setPage] = useState(window.location.hash === ROUTE ? "builder" : "home");

  useEffect(() => {
    const onHash = () => setPage(window.location.hash === ROUTE ? "builder" : "home");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const goBuilder = () => { window.location.hash = ROUTE; };
  const goHome = () => { window.location.hash = ""; };

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Flame size={21} /></div>
          <div><strong>ANP STUDIO</strong><span>VIDEO WORKSPACE</span></div>
        </div>
        <div className="sidebar-caption">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          <button className={page === "home" ? "nav-item active" : "nav-item"} onClick={goHome}>
            <Clapperboard size={17} /><span>Video Generator</span>
          </button>
          <button className={page === "builder" ? "nav-item active" : "nav-item"} onClick={goBuilder}>
            <LayoutTemplate size={17} /><span>Template Builder</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-status"><span className="status-dot" /> LOCAL WORKSPACE</div>
          <span>ANP Engine Clipper</span>
        </div>
      </aside>
      <main className="app-main">
        <div className="topbar">
          <div className="topbar-context"><span>ANP STUDIO</span><span className="topbar-separator">/</span><strong>{page === "builder" ? "Template Builder" : "Video Generator"}</strong></div>
          <div className="topbar-pill"><Sparkles size={14} /> DARK PREMIUM</div>
        </div>
        <div className="page-content">
          {page === "builder" ? <TemplateBuilder onBack={goHome} /> : <Home onOpenBuilder={goBuilder} />}
        </div>
      </main>
    </div>
  );
}
