import { useEffect, useState } from "react";
import { BookOpen, Bot, LayoutDashboard, Map as MapIcon, Network, Workflow } from "lucide-react";
import { getJSON, type Health } from "./api";
import Dashboard from "./components/Dashboard";
import AssistantDrawer, { type AssistTab } from "./components/AssistantDrawer";
import NetworkMap from "./components/NetworkMap";
import { DataFlowModal, OutcomeMapModal, ProblemSolutionModal } from "./components/Modals";

type ModalKey = "ps" | "om" | "flow" | null;
type Page = "command" | "map";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalKey>(null);
  const [assistOpen, setAssistOpen] = useState(false);
  const [assistTab, setAssistTab] = useState<AssistTab>("agent");
  const [page, setPage] = useState<Page>("command");

  useEffect(() => {
    getJSON<Health>("/api/health")
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  const agentOn = !!health?.agent_configured;
  const genieOn = !!health?.genie_configured;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="eyebrow">
            <span className={`dot ${agentOn ? "" : "off"}`} />
            {agentOn ? "AGENT LIVE" : "AGENT NOT CONFIGURED"} · {health?.catalog ?? "…"}
          </div>
          <h1>
            MedTech <span className="coral">Weatherwise</span> Agent <span className="tagline">- Intelligent Supply Chain</span>
          </h1>
          <p>Cold-chain escalation for surgical supplies. Protect every temperature-controlled shipment in transit.</p>
        </div>
        <div className="actions">
          <div className="page-tabs">
            <button className={page === "command" ? "on" : ""} onClick={() => setPage("command")}>
              <LayoutDashboard size={13} /> Command Center
            </button>
            <button className={page === "map" ? "on" : ""} onClick={() => setPage("map")}>
              <MapIcon size={13} /> Network Map
            </button>
          </div>
          <button className="btn" onClick={() => setModal("ps")}>
            <BookOpen size={13} /> Problem &amp; Solution
          </button>
          <button className="btn" onClick={() => setModal("om")}>
            <Network size={13} /> Outcome Maps
          </button>
          <button className="btn" onClick={() => setModal("flow")}>
            <Workflow size={13} /> Data Flow
          </button>
          <button className={`btn coral-solid ${assistOpen ? "active" : ""}`} onClick={() => setAssistOpen((o) => !o)}>
            <Bot size={13} /> Ask WeatherWise
          </button>
        </div>
      </header>

      {healthError && <div className="notice" style={{ margin: 16 }}>Could not reach the API: {healthError}</div>}

      <div className="body-row">
      <div className="stage">
        {page === "command" ? (
          <main className="command">
            <Dashboard catalog={health?.catalog ?? ""} warehouseOk={health ? health.warehouse_configured : null} />
          </main>
        ) : (
          <main className="map-main">
            <NetworkMap warehouseOk={health ? health.warehouse_configured : null} />
          </main>
        )}
      </div>
      <AssistantDrawer
        open={assistOpen}
        tab={assistTab}
        onTab={setAssistTab}
        onClose={() => setAssistOpen(false)}
        agentEnabled={agentOn}
        genieEnabled={genieOn}
      />
      </div>

      {!assistOpen && (
        <button className="assist-fab" onClick={() => setAssistOpen(true)} aria-label="Open WeatherWise assistant">
          <Bot size={18} />
          <span>Ask WeatherWise</span>
        </button>
      )}


      {modal === "ps" && <ProblemSolutionModal onClose={() => setModal(null)} />}
      {modal === "om" && <OutcomeMapModal onClose={() => setModal(null)} />}
      {modal === "flow" && <DataFlowModal onClose={() => setModal(null)} />}
    </div>
  );
}
