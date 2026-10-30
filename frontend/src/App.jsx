import { useEffect, useState } from "react";
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

  return page === "builder" ? <TemplateBuilder onBack={goHome} /> : <Home onOpenBuilder={goBuilder} />;
}
