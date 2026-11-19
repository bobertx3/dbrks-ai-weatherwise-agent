import { Bot, MessageSquareText, X } from "lucide-react";
import AgentChat from "./AgentChat";
import GeniePanel from "./GeniePanel";

export type AssistTab = "agent" | "genie";

/**
 * One slide-out for both assistants, available on every page.
 * The agent *acts* (tools, SOPs, alerts); Genie *answers* data questions with SQL.
 * Both panels stay mounted so conversations survive tab and page switches.
 */
export default function AssistantDrawer({
  open,
  tab,
  onTab,
  onClose,
  agentEnabled,
  genieEnabled,
  pending,
}: {
  open: boolean;
  tab: AssistTab;
  onTab: (t: AssistTab) => void;
  onClose: () => void;
  agentEnabled: boolean;
  genieEnabled: boolean;
  pending?: { id: number; text: string } | null;
}) {
  return (
    <aside className={`assist ${open ? "open" : ""} tab-${tab}`} aria-hidden={!open}>
      <div className="assist-head">
        <div className="assist-tabs" role="tablist">
          <button role="tab" aria-selected={tab === "agent"} className={tab === "agent" ? "on agent" : ""} onClick={() => onTab("agent")}>
            <Bot size={14} /> WeatherWise Agent
          </button>
          <button role="tab" aria-selected={tab === "genie"} className={tab === "genie" ? "on genie" : ""} onClick={() => onTab("genie")}>
            <MessageSquareText size={14} /> Ask Genie
          </button>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close assistant">
          <X size={16} />
        </button>
      </div>
      <div className={`assist-panel ${tab === "agent" ? "" : "hidden"}`}>
        <AgentChat enabled={agentEnabled} pending={pending} />
      </div>
      <div className={`assist-panel ${tab === "genie" ? "" : "hidden"}`}>
        <GeniePanel enabled={genieEnabled} />
      </div>
    </aside>
  );
}
