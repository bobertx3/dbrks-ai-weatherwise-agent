import { useState, useRef, useEffect, useCallback } from 'react';
import { SendIcon, Loader2Icon, SparklesIcon, PlusIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GenieResult } from '@/components/genie/genie-result';

interface GenieMessage {
  role: 'user' | 'genie';
  content: string;
  sql?: string;
  columns?: { name: string }[];
  rows?: any[][];
  narrative?: string;
  error?: string;
}

function getFollowUpQuestions(lastMsg: GenieMessage): string[] {
  const text = (lastMsg.narrative ?? lastMsg.content ?? '').toLowerCase();

  if (text.includes('delay') || text.includes('shipment')) {
    return [
      'What suppliers are associated with delayed shipments?',
      'Show temperature ranges for delayed shipments',
      'Which carriers have the most delays?',
    ];
  }
  if (text.includes('inventory') || text.includes('on_hand') || text.includes('site')) {
    return [
      'Which products are running low on stock?',
      'Show lot expiry dates for all inventory',
      'Compare inventory across all sites',
    ];
  }
  if (text.includes('supplier') || text.includes('tier')) {
    return [
      'Show shipments from Tier-1 suppliers',
      'Which suppliers have products in inventory?',
      'List supplier contact details',
    ];
  }
  return [
    'Which shipments are currently delayed?',
    'Show inventory levels by site',
    'List all Tier-1 suppliers',
  ];
}

const SAMPLE_QUESTIONS = [
  'Which shipments are currently delayed?',
  'Show inventory levels by distribution site',
  'List all Tier-1 suppliers with contact info',
  'What products have the lowest on-hand inventory?',
];

export default function GeniePage() {
  const [messages, setMessages] = useState<GenieMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [genieEnabled, setGenieEnabled] = useState<boolean | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/genie/config', { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => setGenieEnabled(d.enabled))
      .catch(() => setGenieEnabled(false));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: GenieMessage = { role: 'user', content: text };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setLoading(true);

      try {
        let convId = conversationId;
        let messageId: string;

        if (!convId) {
          // Start a new conversation (first message)
          const res = await fetch('/api/genie/start-conversation', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text }),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.message ?? `HTTP ${res.status}`);
          }
          const data = await res.json();
          convId = data.conversation_id;
          messageId = data.message_id;
          if (!convId || !messageId) throw new Error('Failed to start conversation');
          setConversationId(convId);
        } else {
          // Follow-up message in existing conversation
          const res = await fetch(
            `/api/genie/conversations/${convId}/messages`,
            {
              method: 'POST',
              credentials: 'include',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ content: text }),
            },
          );
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.message ?? `HTTP ${res.status}`);
          }
          const data = await res.json();
          messageId = data.message_id ?? data.id;
          if (!messageId) throw new Error('Failed to send message');
        }

        // Poll for completion
        let attempts = 0;
        const maxAttempts = 30;
        while (attempts < maxAttempts) {
          await new Promise((r) => setTimeout(r, 2000));
          attempts++;

          const statusRes = await fetch(
            `/api/genie/conversations/${convId}/messages/${messageId}`,
            { credentials: 'include' },
          );
          const statusData = await statusRes.json();
          const status = statusData.status;

          if (status === 'COMPLETED') {
            // Try to get query result
            let sql: string | undefined;
            let columns: { name: string }[] | undefined;
            let rows: any[][] | undefined;
            let narrative: string | undefined;

            // Extract from attachments
            const attachments = statusData.attachments ?? [];
            for (const att of attachments) {
              if (att.query) {
                sql = att.query.query;
              }
              if (att.text) {
                narrative = att.text.content;
              }
            }

            // Try to get query result if we have a query
            if (sql) {
              try {
                const qrRes = await fetch(
                  `/api/genie/conversations/${convId}/messages/${messageId}/query-result`,
                  { credentials: 'include' },
                );
                if (qrRes.ok) {
                  const qrData = await qrRes.json();
                  columns =
                    qrData.statement_response?.manifest?.schema?.columns;
                  rows = qrData.statement_response?.result?.data_array;
                }
              } catch {
                // Query result not available yet, that's ok
              }
            }

            const genieMsg: GenieMessage = {
              role: 'genie',
              content: narrative ?? 'Query completed.',
              sql,
              columns,
              rows,
              narrative,
            };
            setMessages((prev) => [...prev, genieMsg]);
            setLoading(false);
            return;
          }

          if (status === 'FAILED') {
            throw new Error(statusData.error?.message ?? 'Genie query failed');
          }
        }

        throw new Error('Timed out waiting for Genie response');
      } catch (error) {
        const errorMsg: GenieMessage = {
          role: 'genie',
          content: 'Something went wrong.',
          error: error instanceof Error ? error.message : String(error),
        };
        setMessages((prev) => [...prev, errorMsg]);
        setLoading(false);
      }
    },
    [conversationId, loading],
  );

  if (genieEnabled === null) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      </div>
    );
  }

  if (!genieEnabled) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md text-center space-y-3">
          <SparklesIcon className="h-10 w-10 mx-auto text-muted-foreground" />
          <h2 className="text-lg font-semibold">Ask Genie Not Configured</h2>
          <p className="text-sm text-muted-foreground">
            Run <code className="rounded bg-muted px-1.5 py-0.5 text-xs">./genie/setup_genie_space.sh</code> to
            create a Genie Space, then add <code className="rounded bg-muted px-1.5 py-0.5 text-xs">DATABRICKS_GENIE_SPACE_ID</code> to
            your environment and redeploy.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {messages.length === 0 && (
            <div className="mt-16 text-center space-y-6">
              <div>
                <SparklesIcon className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                <h2 className="text-xl font-semibold">Ask Genie</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Ask natural language questions about your supply chain data
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 max-w-lg mx-auto">
                {SAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="rounded-lg border p-3 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className="mb-4">
              {msg.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground max-w-[80%]">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <SparklesIcon className="h-3 w-3" />
                    Genie
                  </div>
                  {msg.error ? (
                    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                      {msg.error}
                    </div>
                  ) : (
                    <GenieResult
                      sql={msg.sql}
                      columns={msg.columns}
                      rows={msg.rows}
                      narrative={msg.narrative}
                    />
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2Icon className="h-4 w-4 animate-spin" />
              Genie is thinking...
            </div>
          )}

          {!loading && messages.length > 0 && messages[messages.length - 1].role === 'genie' && (
            <div className="flex flex-wrap gap-2">
              {getFollowUpQuestions(messages[messages.length - 1]).map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="rounded-lg border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t bg-background px-4 py-3">
        <div className="mx-auto max-w-4xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your supply chain data..."
              className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              disabled={loading}
            />
            <Button
              type="submit"
              size="icon"
              disabled={loading || !input.trim()}
            >
              {loading ? (
                <Loader2Icon className="h-4 w-4 animate-spin" />
              ) : (
                <SendIcon className="h-4 w-4" />
              )}
            </Button>
            {messages.length > 0 && (
              <Button
                type="button"
                variant="outline"
                size="icon"
                title="New conversation"
                onClick={() => {
                  setMessages([]);
                  setConversationId(null);
                  setInput('');
                }}
              >
                <PlusIcon className="h-4 w-4" />
              </Button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
