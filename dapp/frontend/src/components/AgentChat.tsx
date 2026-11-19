import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  AlertCircle, BellRing, Check, ChevronRight, CloudSun, Database, FileSearch, Loader2, Mail, MessageSquare,
  RotateCcw, Send, Thermometer, Warehouse,
} from "lucide-react";
import Markdown from "./Markdown";
import { streamNDJSON, type ChatMessage, type ToolStep } from "../api";

const STARTERS = [
  "Are there shipments headed to NYC that are at risk due to weather excursions? If so, look up the supplier SOPs so I can resolve them, and send me a summary email with next steps, plus a short SMS if anything is urgent.",
  "Which NYC shipments are at risk tomorrow?",
  "Are any shipments to Nashville at risk from tomorrow's weather?",
  "Are any shipments to Evanston, Illinois at risk from tomorrow's weather?",
  "Find backup stock for the at-risk shipments.",
  "Email me the escalation steps.",
];

type Turn = ChatMessage & { live?: boolean; startedAt?: number; endedAt?: number };

/** pending: a prompt pushed from elsewhere (e.g. a table row's "Ask"); sent once per id. */
export default function AgentChat({ enabled, pending }: { enabled: boolean; pending?: { id: number; text: string } | null }) {
  const [messages, setMessages] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const lastPending = useRef<number | null>(null);
  useEffect(() => {
    if (!pending || pending.id === lastPending.current || !enabled) return;
    lastPending.current = pending.id;
    send(pending.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, enabled]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy || !enabled) return;
    const history = [...messages, { role: "user" as const, content }];
    setMessages([...history, { role: "assistant", content: "", steps: [], live: true, startedAt: Date.now() }]);
    setDraft("");
    setBusy(true);

    // Update the in-flight assistant turn (always the last message).
    const patch = (fn: (t: Turn) => Turn) =>
      setMessages((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);

    try {
      await streamNDJSON("/api/agent/stream", { messages: history.map(({ role, content }) => ({ role, content })) }, (e) => {
        if (e.type === "call") {
          patch((t) => ({ ...t, steps: [...(t.steps ?? []), { id: e.id, name: e.name, args: e.args, output: null, startedAt: Date.now() }] }));
        } else if (e.type === "output") {
          patch((t) => ({
            ...t,
            steps: (t.steps ?? []).map((s) => (s.id === e.id ? { ...s, output: e.output, rows: e.rows, endedAt: Date.now() } : s)),
          }));
        } else if (e.type === "text") {
          patch((t) => ({ ...t, content: t.content ? `${t.content}\n\n${e.text}` : e.text }));
        } else if (e.type === "error") {
          patch((t) => ({ ...t, content: `${t.content ? t.content + "\n\n" : ""}Agent error: ${e.detail}` }));
        }
      });
    } catch (err) {
      patch((t) => ({ ...t, content: `Agent error: ${(err as Error).message}` }));
    } finally {
      patch((t) => ({ ...t, live: false, endedAt: Date.now(), content: t.content || "(no answer)" }));
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
              {m.steps && m.steps.length > 0 && <StepList steps={m.steps} live={!!m.live} startedAt={m.startedAt} endedAt={m.endedAt} />}
              {m.content ? (
                <div className="turn-a agent">
                  <Markdown text={m.content} />
                </div>
              ) : (
                m.live && (
                  <div className="thinking">
                    <span className="dot coral" /> {m.steps?.length ? "WORKING THROUGH THE STEPS…" : "PLANNING…"}
                  </div>
                )
              )}
            </div>
          ),
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

// ── Tool steps ───────────────────────────────────────────────────────────────
type Meta = { title: string; source: string; desc: string; icon: typeof Database; kind: "uc" | "vs" | "api" | "action" };

const TOOLS: Record<string, Meta> = {
  get_shipments: { title: "Pull live shipments", source: "Unity Catalog function", kind: "uc", icon: Database,
    desc: "Reads shipment status, ETA, sensor temperature, product range and surgery date from governed tables." },
  check_weather: { title: "Check destination forecast", source: "Open-Meteo weather API", kind: "api", icon: CloudSun,
    desc: "Current conditions plus a 7-day high/low for the destination city, so the ETA day is covered." },
  temp_gap: { title: "Compute temperature gap", source: "Unity Catalog function", kind: "uc", icon: Thermometer,
    desc: "Temperature minus the product's allowed limit. Rules, not AI." },
  get_backup_inventory: { title: "Find backup stock", source: "Unity Catalog function", kind: "uc", icon: Warehouse,
    desc: "On-hand units of the product, nearest sites to the destination first." },
  get_supplier_details: { title: "Look up supplier", source: "Unity Catalog function", kind: "uc", icon: Database,
    desc: "Supplier contacts and escalation tier." },
  search_supplier_sops: { title: "Search supplier SOPs", source: "Databricks Vector Search", kind: "vs", icon: FileSearch,
    desc: "Finds the SOP passages for this product's excursion handling, so every action has a source." },
  send_email: { title: "Send escalation email", source: "Mailgun", kind: "action", icon: Mail,
    desc: "Emails the escalation summary to the on-call recipient." },
  send_sms: { title: "Send SMS alert", source: "Twilio", kind: "action", icon: MessageSquare,
    desc: "Texts a short risk summary." },
  send_connect_sms: { title: "Send LinkedIn connect text", source: "Twilio MMS", kind: "action", icon: BellRing,
    desc: "Greeting text, then the LinkedIn QR code." },
};

/** bldemos__agentbricks_weatherwise__get_shipments -> get_shipments */
const shortName = (n: string) => n.split("__").pop() ?? n;

function metaOf(name: string): Meta {
  const n = shortName(name);
  return TOOLS[n] ?? { title: n.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), source: "Tool", kind: "uc", icon: Database, desc: "" };
}

/** UC function outputs arrive as {"format": "CSV"|"SCALAR", "value": ...}. */
function ucValue(output: string | null): { format?: string; value: string } {
  if (!output) return { value: "" };
  try {
    const j = JSON.parse(output);
    if (j && typeof j === "object" && "value" in j) return { format: j.format, value: String(j.value ?? "") };
  } catch { /* plain text */ }
  return { value: output };
}

function csvRows(output: string | null): string[][] {
  const { value } = ucValue(output);
  return value.split("\n").filter(Boolean).map((l) => l.split(","));
}

function args(step: ToolStep): Record<string, unknown> {
  try { return JSON.parse(step.args || "{}"); } catch { return {}; }
}

const isError = (s: ToolStep) => !!s.output && /^(❌|Error calling tool|Error)/.test(s.output.trim());

function tomorrowISO() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
}

/** One-line result for a group of calls to the same tool. */
function summarize(name: string, steps: ToolStep[]): string {
  const done = steps.filter((s) => s.output != null);
  if (done.length === 0) return "";
  const n = shortName(name);
  if (n === "get_shipments") {
    const rows = done[0].rows ?? Math.max(0, csvRows(done[0].output).length - 1);
    const city = args(done[0]).dest_city;
    return `${rows} shipment${rows === 1 ? "" : "s"}${city ? ` · ${city}` : ""}`;
  }
  if (n === "check_weather") {
    return done.map((s) => {
      const out = s.output ?? "";
      const now = out.match(/Now:\s*(-?[\d.]+)°F/)?.[1];
      const tm = out.match(new RegExp(`${tomorrowISO()}:\\s*(-?[\\d.]+)°F\\s*/\\s*(-?[\\d.]+)°F`));
      const city = String(args(s).city ?? "");
      return [city, now && `now ${Math.round(+now)}°F`, tm && `tomorrow ${Math.round(+tm[1])}° / ${Math.round(+tm[2])}°F`].filter(Boolean).join(" · ");
    }).join("  |  ");
  }
  if (n === "temp_gap") {
    const gaps = done.map((s) => parseFloat(ucValue(s.output).value)).filter((v) => !Number.isNaN(v));
    if (!gaps.length) return `${done.length} computed`;
    const max = Math.max(...gaps);
    return `${gaps.length} gap${gaps.length === 1 ? "" : "s"} · largest ${max > 0 ? "+" : ""}${max.toFixed(1)}°F`;
  }
  if (n === "get_backup_inventory") {
    const firsts = done.map((s) => csvRows(s.output)).filter((r) => r.length > 1);
    if (!firsts.length) return "No backup stock found";
    const [h, top] = firsts[0];
    const site = top[h.indexOf("site_name")];
    const qty = top[h.indexOf("on_hand_qty")];
    return `${done.length} product${done.length === 1 ? "" : "s"} · nearest: ${site}${qty ? ` (${qty} units)` : ""}`;
  }
  if (n === "get_supplier_details") {
    const people = done.flatMap((s) => {
      const [h, ...rest] = csvRows(s.output);
      if (!h) return [];
      const ci = h.indexOf("contact_name"), si = h.indexOf("supplier_name");
      return rest.map((r) => `${r[ci]} (${r[si]})`);
    });
    const uniq = [...new Set(people)];
    return uniq.length ? `${uniq.length} supplier${uniq.length === 1 ? "" : "s"} · ${uniq.slice(0, 2).join(", ")}${uniq.length > 2 ? "…" : ""}` : "No supplier found";
  }
  if (n === "search_supplier_sops") return `${done.length} search${done.length === 1 ? "" : "es"} · SOP passages retrieved`;
  const last = ucValue(done[done.length - 1].output);
  if (last.format === "CSV") {
    const n = Math.max(0, last.value.split("\n").filter(Boolean).length - 1);
    return `${n} row${n === 1 ? "" : "s"}`;
  }
  return last.value.split("\n")[0].slice(0, 120);
}

type Group = { name: string; steps: ToolStep[] };

/** Consecutive calls to the same tool become one card (e.g. temp_gap ×5). */
function groupSteps(steps: ToolStep[]): Group[] {
  const out: Group[] = [];
  for (const s of steps) {
    const last = out[out.length - 1];
    if (last && shortName(last.name) === shortName(s.name)) last.steps.push(s);
    else out.push({ name: s.name, steps: [s] });
  }
  return out;
}

const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

function StepList({ steps, live, startedAt, endedAt }: { steps: ToolStep[]; live: boolean; startedAt?: number; endedAt?: number }) {
  const [open, setOpen] = useState(false);
  const groups = groupSteps(steps);
  const expanded = live || open;
  return (
    <div className={`steps ${live ? "live" : ""}`}>
      {!live && (
        <button className="steps-head" onClick={() => setOpen((o) => !o)}>
          <Check size={13} className="ok" />
          <span>Ran {groups.length} step{groups.length === 1 ? "" : "s"} · {steps.length} tool call{steps.length === 1 ? "" : "s"}</span>
          {startedAt && endedAt && <span className="muted">· {secs(endedAt - startedAt)}</span>}
          <span className="steps-toggle">{open ? "Hide steps" : "Show steps"}</span>
        </button>
      )}
      {expanded && (
        <ol className="step-list">
          {groups.map((g, i) => <StepCard key={i} group={g} />)}
        </ol>
      )}
    </div>
  );
}

function StepCard({ group }: { group: Group }) {
  const [open, setOpen] = useState(false);
  const meta = metaOf(group.name);
  const Icon = meta.icon;
  const running = group.steps.some((s) => s.output == null);
  const failed = group.steps.some(isError);
  const started = Math.min(...group.steps.map((s) => s.startedAt ?? Infinity));
  const ended = Math.max(...group.steps.map((s) => s.endedAt ?? 0));
  const summary = summarize(group.name, group.steps);
  return (
    <li className={`step ${meta.kind}`}>
      <div className="step-icon"><Icon size={15} /></div>
      <div className="step-main">
        <div className="step-top">
          <span className="step-title">{meta.title}</span>
          <code className="step-tool">{shortName(group.name)}{group.steps.length > 1 && ` ×${group.steps.length}`}</code>
          <span className={`step-status ${running ? "running" : failed ? "failed" : "done"}`}>
            {running ? <><Loader2 size={11} className="spin" /> Running</> : failed ? <><AlertCircle size={11} /> Error</> : <><Check size={11} /> Done</>}
            {!running && Number.isFinite(started) && ended > 0 && <span className="step-time">{secs(ended - started)}</span>}
          </span>
        </div>
        <div className="step-sub">{[summary, meta.source].filter(Boolean).join(" · ")}</div>
        {meta.desc && <div className="step-desc">{meta.desc}</div>}
        <button className="step-more" onClick={() => setOpen((o) => !o)}>
          <ChevronRight size={12} className={open ? "rot" : ""} /> Request &amp; response
        </button>
        {open && (
          <div className="step-io">
            {group.steps.map((s, i) => (
              <div className="io-pair" key={i}>
                <div>
                  <div className="io-lbl">Request <span className="mono">{shortName(s.name)}</span></div>
                  <pre className="io-code">{pretty(s.args)}</pre>
                </div>
                <div>
                  <div className="io-lbl">Response</div>
                  <pre className="io-code">{s.output == null ? "…" : prettyOut(s.output)}</pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

function pretty(text: string) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

function prettyOut(text: string) {
  const { format, value } = ucValue(text);
  return format ? value : pretty(text);
}
