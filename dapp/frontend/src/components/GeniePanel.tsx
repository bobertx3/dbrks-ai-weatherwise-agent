import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Code2, RotateCcw, Send, Table2 } from "lucide-react";
import { postJSON, type GenieResult } from "../api";
import Markdown from "./Markdown";

type Turn = { question: string; result?: GenieResult; error?: string };

const SAMPLES = [
  "Which shipments are delayed?",
  "Which sites hold the most on-hand units?",
  "Which lots expire in the next 90 days?",
  "What is the average max temperature by carrier?",
];

/** Genie conversation, rendered inside the shared assistant drawer (AssistantDrawer). */
export default function GeniePanel({ enabled }: { enabled: boolean }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy || !enabled) return;
    setDraft("");
    setTurns((t) => [...t, { question }]);
    setBusy(true);
    try {
      const result = await postJSON<GenieResult>("/api/genie/ask", { question, conversation_id: conversationId });
      setConversationId(result.conversation_id);
      setTurns((t) => replaceLast(t, { question, result }));
    } catch (e) {
      setTurns((t) => replaceLast(t, { question, error: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setTurns([]);
    setConversationId(undefined);
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(draft);
    }
  }

  return (
    <>
      <div className="assist-tool-row">
        <span className="assist-sub">Natural-language questions answered with SQL on the governed supply chain tables.</span>
        <button className="icon-btn" onClick={reset} disabled={busy || turns.length === 0} aria-label="New conversation" title="New conversation">
          <RotateCcw size={15} />
        </button>
      </div>

        <div className="assist-body">
          {turns.length === 0 && (
            <div className="suggest">
              {SAMPLES.map((s) => (
                <button key={s} onClick={() => ask(s)} disabled={!enabled}>
                  {s}
                </button>
              ))}
            </div>
          )}
          {turns.map((t, i) => (
            <TurnView key={i} turn={t} onAsk={ask} />
          ))}
          {busy && (
            <div className="thinking">
              <span className="dot" /> GENIE IS QUERYING…
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="drawer-foot">
          <div className="input-wrap">
            <textarea
              className="input"
              rows={2}
              placeholder="Ask a question about the supply chain data…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              disabled={!enabled}
            />
            <button className="send" onClick={() => ask(draft)} disabled={!enabled || busy || !draft.trim()} aria-label="Send">
              <Send size={15} />
            </button>
          </div>
          {!enabled && <div className="hint">GENIE SPACE NOT CONFIGURED</div>}
        </div>
    </>
  );
}

function TurnView({ turn, onAsk }: { turn: Turn; onAsk: (q: string) => void }) {
  const [showSql, setShowSql] = useState(false);
  // Small results are the answer, so show them open; large ones start collapsed.
  const [showRows, setShowRows] = useState((turn.result?.rows.length ?? 0) > 0 && (turn.result?.rows.length ?? 0) <= 25);
  return (
    <>
      <div className="turn-q">{turn.question}</div>
      {turn.error && <div className="turn-a error">{turn.error}</div>}
      {turn.result && (
        <div>
          <div className="turn-a"><Markdown text={turn.result.text} /></div>
          <div className="toggles">
            {turn.result.sql && (
              <button className={`toggle ${showSql ? "open" : ""}`} onClick={() => setShowSql((s) => !s)}>
                <Code2 size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} />
                SQL
              </button>
            )}
            {turn.result.rows.length > 0 && (
              <button className={`toggle ${showRows ? "open" : ""}`} onClick={() => setShowRows((s) => !s)}>
                <Table2 size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} />
                {showRows ? "HIDE" : "SHOW"} RESULT · {turn.result.rows.length} {turn.result.rows.length === 1 ? "ROW" : "ROWS"}
              </button>
            )}
          </div>
          {showSql && turn.result.sql && <pre className="sql">{turn.result.sql}</pre>}
          {showRows && turn.result.rows.length > 0 && (
            <div className="result-wrap">
              <table>
                <thead>
                  <tr>
                    {turn.result.columns.map((c, j) => (
                      <th key={c} className={isNumericCol(turn.result!.rows, j) ? "num" : ""}>{prettyCol(c)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {turn.result.rows.slice(0, 100).map((r, i) => (
                    <tr key={i}>
                      {r.map((v, j) => {
                        const num = isNumericCol(turn.result!.rows, j);
                        return <td key={j} className={num ? "num" : ""}>{formatCell(v, num)}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {turn.result.suggested_questions.length > 0 && (
            <div className="suggest" style={{ marginTop: 10 }}>
              {turn.result.suggested_questions.map((q) => (
                <button key={q} onClick={() => onAsk(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}

const isNum = (v: unknown) => v != null && v !== "" && !Number.isNaN(Number(v));

function isNumericCol(rows: unknown[][], j: number): boolean {
  const vals = rows.map((r) => r[j]).filter((v) => v != null && v !== "");
  return vals.length > 0 && vals.every(isNum);
}

function formatCell(v: unknown, numeric: boolean): string {
  if (v == null || v === "") return "—";
  if (numeric) {
    const n = Number(v);
    return Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(v);
}

/** on_hand_units -> On hand units */
function prettyCol(c: string): string {
  const s = c.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function replaceLast(turns: Turn[], next: Turn): Turn[] {
  return [...turns.slice(0, -1), next];
}
