import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { BellRing, CloudSun, Database, FileSearch, RotateCcw, Send } from "lucide-react";
import Markdown from "./Markdown";
import { postJSON, type ChatMessage, type ToolStep } from "../api";

const STARTERS = [
  "Which shipments are at risk from weather, and what should we do first?",
  "Find backup inventory near the delayed shipments.",
  "What does the SOP say to do when a cold-chain load is delayed?",
];

export default function AgentChat({ enabled }: { enabled: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy || !enabled) return;
    const next: ChatMessage[] = [...messages, { role: "user", content }];
    setMessages(next);
    setDraft("");
    setBusy(true);
    try {
      const res = await postJSON<{ content: string; steps: ToolStep[] }>("/api/agent/chat", {
        messages: next.map(({ role, content }) => ({ role, content })),
      });
      setMessages((m) => [...m, { role: "assistant", content: res.content, steps: res.steps }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Agent error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  }

  return (
    <>
      <div className="assist-tool-row">
        <span className="assist-sub">Forecasts · telemetry · inventory · SOPs · alerts. A person approves every escalation.</span>
        <button className="icon-btn" onClick={() => setMessages([])} disabled={busy || messages.length === 0} aria-label="New chat" title="New chat">
          <RotateCcw size={15} />
        </button>
      </div>

      <div className="assist-body">
        {!enabled && <div className="notice">The agent serving endpoint is not configured.</div>}
        {messages.length === 0 && (
          <div className="suggest">
            {STARTERS.map((s) => (
              <button key={s} onClick={() => send(s)} disabled={!enabled}>
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="turn-q">{m.content}</div>
          ) : (
            <div key={i} className="agent-turn">
              <div className="agent-who">
                <span className="agent-mark" aria-hidden>W</span> WEATHERWISE
              </div>
              <div className="turn-a agent">
                <Markdown text={m.content} />
              </div>
              {m.steps && m.steps.length > 0 && <ToolTrace steps={m.steps} />}
            </div>
          ),
        )}

        {busy && (
          <div className="thinking">
            <span className="dot coral" /> WEATHERWISE IS CHECKING FORECASTS, SHIPMENTS AND SOPS…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="drawer-foot">
        <div className="input-wrap">
          <textarea
            className="input"
            placeholder="Ask about at-risk shipments, backup stock, or SOP steps…"
            value={draft}
            rows={2}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            disabled={!enabled}
          />
          <button className="send coral" onClick={() => send(draft)} disabled={!enabled || busy || !draft.trim()} aria-label="Send">
            <Send size={15} />
          </button>
        </div>
        <div className="hint">ENTER TO SEND · SHIFT+ENTER FOR NEW LINE</div>
      </div>
    </>
  );
}

// ── Tool trace ───────────────────────────────────────────────────────────────
type Kind = "uc" | "vs" | "api" | "action";
const KIND: Record<Kind, { label: string; icon: typeof Database }> = {
  uc: { label: "UC function", icon: Database },
  vs: { label: "Vector Search", icon: FileSearch },
  api: { label: "Weather API", icon: CloudSun },
  action: { label: "Alert", icon: BellRing },
};

/** bldemos__agentbricks_weatherwise__get_shipments -> get_shipments */
const shortName = (n: string) => n.replace(/^[A-Za-z0-9-]+__[A-Za-z0-9-]+__/, "");

function kindOf(raw: string): Kind {
  const n = shortName(raw);
  if (n === "check_weather") return "api";
  if (n === "search_supplier_sops") return "vs";
  if (n === "send_email" || n === "send_sms") return "action";
  return "uc";
}

function ToolTrace({ steps }: { steps: ToolStep[] }) {
  const [open, setOpen] = useState(false);
  // Group repeated calls (e.g. check_weather ×17) in first-use order.
  const groups: { name: string; kind: Kind; count: number }[] = [];
  for (const s of steps) {
    const name = shortName(s.name);
    const g = groups.find((x) => x.name === name);
    if (g) g.count += 1;
    else groups.push({ name, kind: kindOf(s.name), count: 1 });
  }
  return (
    <div className="trace">
      <button className={`trace-head ${open ? "open" : ""}`} onClick={() => setOpen((o) => !o)}>
        <span className="lbl">TOOL CALLS</span>
        <span className="trace-sum">
          {groups.length} {groups.length === 1 ? "tool" : "tools"} · {steps.length} {steps.length === 1 ? "call" : "calls"}
        </span>
        <span className="trace-toggle">{open ? "HIDE STEPS" : "SHOW STEPS"}</span>
      </button>
      <div className="trace-chips">
        {groups.map((g) => {
          const Icon = KIND[g.kind].icon;
          return (
            <span key={g.name} className={`tchip ${g.kind}`} title={KIND[g.kind].label}>
              <Icon size={11} /> {g.name}
              {g.count > 1 && <b>×{g.count}</b>}
            </span>
          );
        })}
      </div>
      {open && (
        <ol className="trace-steps">
          {steps.map((s, i) => (
            <li key={i} className={kindOf(s.name)}>
              <div className="ts-name">
                <span className="ts-n">{i + 1}</span> {shortName(s.name)}
                <span className="ts-kind">{KIND[kindOf(s.name)].label}</span>
              </div>
              {s.args && <code className="ts-args">{s.args}</code>}
              {s.output && <pre className="ts-out">{s.output}</pre>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
