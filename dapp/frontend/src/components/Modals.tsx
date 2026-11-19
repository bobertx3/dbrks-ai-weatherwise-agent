import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

function Modal({ title, subtitle, onClose, children, footer, wide, compact }: {
  title: ReactNode;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: string;
  wide?: boolean;
  /** Slim one-line header so diagrams get the vertical space. */
  compact?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-root" role="dialog" aria-modal="true">
      <div className="modal-scrim" onClick={onClose} />
      <div className={`modal ${wide ? "wide" : ""} ${compact ? "compact" : ""}`}>
        <div className="modal-head">
          {compact ? (
            <div className="modal-head-line">
              <h2>{title}</h2>
              {subtitle && <p>{subtitle}</p>}
            </div>
          ) : (
            <div>
              <div className="lbl">MedTech Weatherwise Agent</div>
              <h2 style={{ marginTop: 6 }}>{title}</h2>
              {subtitle && <p>{subtitle}</p>}
            </div>
          )}
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

// Exec-demo copy: short enough to read from across the room.
const SHIFTS: [string, string][] = [
  ["Temperature risk found too late", "Flagged before product spoils"],
  ["Hours of manual triage", "A ranked list in seconds"],
  ["SOPs buried in PDFs", "The right SOP, cited"],
  ["Slow email chains", "Instant email + SMS alert"],
];

export function ProblemSolutionModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Problem & Solution" onClose={onClose} footer="A person approves every escalation. Demo data is synthetic.">
      <div className="ps-hero">
        <div className="ps-hero-box p">
          <div className="ps-tag">PROBLEM</div>
          <p>Temperature-controlled shipments for surgery fail in transit before anyone acts.</p>
          <div className="ps-sub">
            Implants, heart valves, biologics, and vaccines. Heat, storms, or a delay can spoil the product, and the surgery gets postponed.
          </div>
        </div>
        <div className="ps-hero-box s">
          <div className="ps-tag">SOLUTION</div>
          <p>An AI agent that spots at-risk shipments and escalates in seconds.</p>
          <div className="ps-sub">
            Checks forecasts, delays, and temperature limits, then finds backup stock, the supplier SOP, and who to alert.
          </div>
        </div>
      </div>

      <div className="ps-rows">
        {SHIFTS.map(([from, to]) => (
          <div className="ps-row" key={from}>
            <span className="from">{from}</span>
            <span className="arrow" aria-hidden>→</span>
            <span className="to">{to}</span>
          </div>
        ))}
      </div>
    </Modal>
  );
}

const OUTCOME_COLUMNS: { heading: string; cards: [string, "primary" | "secondary" | ""][] }[] = [
  {
    heading: "Increase R&D Productivity",
    cards: [["Accelerate Drug Discovery", ""], ["Streamline Clinical Development", ""], ["Build a FAIR Data Platform", ""]],
  },
  {
    heading: "Optimize Supply Chain & Manufacturing",
    cards: [["Create E2E Supply Chain Visibility", "primary"], ["Implement Smart Manufacturing", ""]],
  },
  {
    heading: "Improve Commercial Effectiveness",
    cards: [["Generate Real World Evidence", ""], ["Deliver Provider Next-Best-Action", ""], ["Personalize Patient Engagement", ""]],
  },
];

const BADGE: Record<string, string> = { primary: "This app" };

export function OutcomeMapModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Outcome Maps" onClose={onClose}>
      <h2 className="om-title">
        <span className="di">Data Intelligence</span> Outcome Maps
      </h2>
      <div className="om-frame">
        <div className="om-tab">Life Sciences</div>
        <div className="om-cols">
          {OUTCOME_COLUMNS.map((col) => (
            <div className="om-col" key={col.heading}>
              <div className="om-h">{col.heading}</div>
              {col.cards.map(([label, tone]) => (
                <div className={`om-card ${tone}`} key={label}>
                  {tone && BADGE[tone] && <span className="om-badge">{BADGE[tone]}</span>}
                  {label}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="om-why">
        <div className="p">
          <b>Create E2E Supply Chain Visibility</b>
          This app. Shipments, inventory, suppliers, and SOPs are governed in Unity Catalog and joined with live
          weather, so at-risk loads are flagged early and a person approves every escalation before it is sent.
        </div>
      </div>
    </Modal>
  );
}

// ── Data Flow (left → right, after the trial-recruitment architecture) ─────
function Box({ title, sub, note, tone }: { title: string; sub?: string; note?: string; tone?: "data" | "agent" | "genie" | "app" | "ml" | "gw" | "llm" | "sem" }) {
  return (
    <div className={`df-box ${tone ? `df-${tone}` : ""}`}>
      <div className="t">{title}</div>
      {sub && <div className="s">{sub}</div>}
      {note && <div className="n">{note}</div>}
    </div>
  );
}

function Link({ label }: { label: string }) {
  return (
    <div className="df-link" aria-hidden>
      <span className="line" />
      <span className="dot" />
      <span className="line" />
      <span className="pulse" />
      <span className="lab">{label}</span>
    </div>
  );
}

const DF_TOOLS: [string, string, string][] = [
  ["get_shipments · get_backup_inventory", "UC functions", "Finds in-transit loads and the nearest backup stock"],
  ["get_supplier_details · temp_gap", "UC functions", "Who to call, and how far over its limit a load is"],
  ["search_supplier_sops", "Vector Search · citations", "Pulls the exact SOP step for this supplier and issue"],
  ["check_weather", "Open-Meteo", "Forecast heat and storms on the route"],
  ["send_email · send_sms", "Mailgun · Twilio", "Alerts the people who own the next step"],
];

export function DataFlowModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal
      title="Data Flow"
      subtitle="Temperature-controlled logistics data to a governed escalation, all on Databricks · bldemos.agentbricks_weatherwise"
      onClose={onClose}
      wide
      compact
      footer="01 load data · 02 UC functions · 03 vector index · 04 evaluate + register · 05 deploy agent · 06 deploy app"
    >
      <div className="df">
        <div className="df-col">
          <div className="lbl">SOURCE DATA (SYNTHETIC)</div>
          <Box title="Shipments" sub="ETA · carrier · max temp" />
          <Box title="Inventory" sub="sites · lots · expiry" />
          <Box title="Suppliers" sub="contacts · escalation" />
          <Box title="Supplier SOPs" sub="escalation documents" />
        </div>

        <Link label="Lakeflow Job" />

        <div className="df-col df-group uc">
          <div className="lbl g">UNITY CATALOG · GOVERNED LAKEHOUSE</div>
          <div className="lbl">DATA</div>
          <Box tone="data" title="Delta tables" sub="shipments · inventory · suppliers · supplier_sops" />
          <div className="lbl">AI ASSETS</div>
          <Box title="Vector Search index" sub="supplier_sops_vs_index" />
          <Box title="UC functions" sub="the agent's governed SQL tools" />
          <div className="df-pair">
            <Box title="Agent model" sub="weatherwise · registered" />
            <Box title="Inference table" sub="weatherwise_payload" />
          </div>
          <div className="lbl">UC SEMANTIC STACK</div>
          <div className="df-pair">
            <Box tone="sem" title="Domains" sub="supply chain operations" />
            <Box tone="sem" title="Pages" sub="curated data products" />
          </div>
          <div className="df-pair">
            <Box tone="sem" title="Metric Views" sub="governed shipment & inventory KPIs" />
            <Box tone="sem" title="Wikis" sub="SOPs & business context" />
          </div>
          <div className="df-chips">
            <span>Table &amp; column descriptions</span><span>Grants</span><span>Lineage</span><span>Inference tables</span><span>AI Gateway logging</span>
          </div>
        </div>

        <Link label="serve" />

        <div className="df-col">
          <Box tone="ml" title="MLflow" sub="evaluation · traces every agent run" />
          <div className="df-group agent">
            <div className="lbl c">MODEL SERVING · AGENT</div>
            <Box tone="agent" title="WeatherWise agent" sub="LangGraph · ResponsesAgent" />
            <div className="df-down" aria-hidden>↓</div>
            <Box tone="gw" title="Unity AI Gateway" sub="model service weatherwise_llm · agent SP EXECUTE · inference table weatherwise_llm_payload" />
            <div className="df-down" aria-hidden>↓</div>
            <Box tone="llm" title="GPT 5.6" sub="system.ai.databricks-gpt-5-6-sol" />
            <div className="lbl">AGENT TOOLS</div>
            {DF_TOOLS.map(([name, sub, note]) => (
              <div className="df-tool" key={name}>
                <div className="t">{name} <span>{sub}</span></div>
                <div className="n">{note}</div>
              </div>
            ))}
          </div>
          <div className="lbl">ANALYTICS</div>
          <Box tone="genie" title="Genie" sub="Supply Chain Explorer · questions → SQL on the same tables" />
        </div>

        <Link label="CAN_QUERY · CAN_RUN" />

        <div className="df-col">
          <div className="lbl">EXPERIENCE</div>
          <Box tone="app" title="Databricks App" sub="dashboard · agent chat · Ask Genie" />
          <Box title="Supply chain coordinator" sub="reviews · approves · escalates" />
        </div>
      </div>
    </Modal>
  );
}
