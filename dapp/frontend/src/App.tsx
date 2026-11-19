import { useEffect, useRef, useState } from "react";
import { BookOpen, Bot, ExternalLink, LayoutDashboard, Mic, Network, Sparkles, Workflow } from "lucide-react";
import { getJSON, type Health } from "./api";
import CommandCenter from "./components/CommandCenter";
import AssistantDrawer, { type AssistTab } from "./components/AssistantDrawer";
import { DataFlowModal, OutcomeMapModal, ProblemSolutionModal } from "./components/Modals";

type ModalKey = "ps" | "om" | "flow" | null;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalKey>(null);
  const [assistOpen, setAssistOpen] = useState(false);
  const [assistTab, setAssistTab] = useState<AssistTab>("agent");
  const [pending, setPending] = useState<{ id: number; text: string } | null>(null);
  const headerRef = useRef<HTMLElement>(null);

  // The header is sticky; publish its height so the drawer and table header can stick just below it.
  useEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() =>
      document.documentElement.style.setProperty("--topbar-h", `${el.getBoundingClientRect().height}px`),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    getJSON<Health>("/api/health")
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  const agentOn = !!health?.agent_configured;
  const genieOn = !!health?.genie_configured;

  return (
    <div className="app">
      <header className="topbar" ref={headerRef}>
        <div className="brand">
          <div className="eyebrow">
            <span className={`dot ${agentOn ? "" : "off"}`} />
            {agentOn ? "AGENT LIVE" : "AGENT NOT CONFIGURED"}<span className="eyebrow-cat"> · {health?.catalog ?? "…"}</span>
          </div>
          <h1>
            MedTech <span className="coral">Weatherwise</span> Agent <span className="tagline">- Intelligent Supply Chain</span>
          </h1>
          <p>Temperature-controlled logistics for surgical supplies. Protect every shipment in transit and escalate before it spoils.</p>
        </div>
        <div className="actions">
          <button
            className="btn"
            title="Open the SA talk track and FAQs in a small window"
            onClick={() => window.open("/talk-track.html", "ww-talk-track", "popup,width=560,height=820,left=40,top=60")}
          >
            <Mic size={13} /> <span className="bl">Talk Track</span>
          </button>
          <button className="btn" onClick={() => setModal("ps")} title="Problem & Solution">
            <BookOpen size={13} /> <span className="bl shrink">Problem &amp; Solution</span>
          </button>
          <button className="btn" onClick={() => setModal("om")} title="Outcome Maps">
            <Network size={13} /> <span className="bl shrink">Outcome Maps</span>
          </button>
          <button className="btn" onClick={() => setModal("flow")} title="Data Flow">
            <Workflow size={13} /> <span className="bl shrink">Data Flow</span>
          </button>
          {health?.dashboard_url && (
            <a className="btn" href={health.dashboard_url} target="_blank" rel="noopener noreferrer" title="Open the WeatherWise AI/BI dashboard (new tab)">
              <LayoutDashboard size={13} /> <span className="bl shrink">Dashboard</span> <ExternalLink size={11} />
            </a>
          )}
          {health?.genie_one_url && (
            <a className="btn genie" href={health.genie_one_url} target="_blank" rel="noopener noreferrer" title="Open Genie One in Databricks (new tab)">
              <Sparkles size={13} /> <span className="bl">Genie One</span> <ExternalLink size={11} />
            </a>
          )}
          <button className={`btn coral-solid ${assistOpen ? "active" : ""}`} onClick={() => setAssistOpen((o) => !o)}>
            <Bot size={13} /> <span className="bl-ask">Ask WeatherWise</span><span className="bl-ask-short">Ask</span>
          </button>
        </div>
      </header>

      {healthError && <div className="notice" style={{ margin: 16 }}>Could not reach the API: {healthError}</div>}

      <div className="body-row">
      <div className="stage">
        <main className="command">
          <CommandCenter
            catalog={health?.catalog ?? ""}
            warehouseOk={health ? health.warehouse_configured : null}
            onAsk={(text) => {
              setAssistTab("agent");
              setAssistOpen(true);
              setPending({ id: Date.now(), text });
            }}
          />
        </main>
      </div>
      <AssistantDrawer
        open={assistOpen}
        tab={assistTab}
        onTab={setAssistTab}
        onClose={() => setAssistOpen(false)}
        agentEnabled={agentOn}
        genieEnabled={genieOn}
        pending={pending}
      />
      </div>




      {modal === "ps" && <ProblemSolutionModal onClose={() => setModal(null)} />}
      {modal === "om" && <OutcomeMapModal onClose={() => setModal(null)} />}
      {modal === "flow" && <DataFlowModal onClose={() => setModal(null)} />}
    </div>
  );
}
