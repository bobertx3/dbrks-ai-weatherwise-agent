import { useEffect, useState } from "react";
import { BookOpen, Bot, ExternalLink, Network, Sparkles, Workflow } from "lucide-react";
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
          <p>Temperature-controlled logistics for surgical supplies. Protect every shipment in transit and escalate before it spoils.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => setModal("ps")}>
            <BookOpen size={13} /> Problem &amp; Solution
          </button>
          <button className="btn" onClick={() => setModal("om")}>
            <Network size={13} /> Outcome Maps
          </button>
          <button className="btn" onClick={() => setModal("flow")}>
            <Workflow size={13} /> Data Flow
          </button>
          {health?.genie_one_url && (
            <a className="btn genie" href={health.genie_one_url} target="_blank" rel="noopener noreferrer" title="Open Genie One in Databricks (new tab)">
              <Sparkles size={13} /> Genie One <ExternalLink size={11} />
            </a>
          )}
          <button className={`btn coral-solid ${assistOpen ? "active" : ""}`} onClick={() => setAssistOpen((o) => !o)}>
            <Bot size={13} /> Ask WeatherWise
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
