import { useState } from 'react';
import { XIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface AgentNode {
  id: string;
  label: string;
  description: string;
  category: 'orchestrator' | 'agent' | 'tool' | 'external';
  color: string;
  borderColor: string;
}

interface FlowConnection {
  from: string;
  to: string;
  label: string;
}

const agents: AgentNode[] = [
  {
    id: 'orchestrator',
    label: 'WeatherWise Agent',
    description: 'Main orchestrator that routes user queries to specialized sub-agents',
    category: 'orchestrator',
    color: 'rgba(234, 179, 8, 0.15)',
    borderColor: '#eab308',
  },
  {
    id: 'meteorologist',
    label: 'Meteorologist',
    description: 'Get the actual weather report for a given city',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
  {
    id: 'sql-analyst',
    label: 'Data/SQL Analyst',
    description: 'Check shipments in-transit, determine risk of delay or damage',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
  {
    id: 'supplier',
    label: 'Supplier Researcher',
    description: 'Look up supplier SLAs and escalations via SOPs',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
  {
    id: 'research',
    label: 'Research Assistant',
    description: 'Write a report for the manager with findings',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
  {
    id: 'email',
    label: 'Draft Email',
    description: 'Draft & send email with info and recommended actions',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
  {
    id: 'sms',
    label: 'Send SMS Alert',
    description: 'Send text message to bring urgency to the matter',
    category: 'agent',
    color: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3b82f6',
  },
];

const tools: AgentNode[] = [
  {
    id: 'check_weather',
    label: 'check_weather',
    description: 'Open-Meteo API — returns current weather for a city',
    category: 'tool',
    color: 'rgba(34, 197, 94, 0.15)',
    borderColor: '#22c55e',
  },
  {
    id: 'get_shipments',
    label: 'get_shipments',
    description: 'Unity Catalog function — retrieve shipment data',
    category: 'tool',
    color: 'rgba(168, 85, 247, 0.15)',
    borderColor: '#a855f7',
  },
  {
    id: 'get_backup_inventory',
    label: 'get_backup_inventory',
    description: 'Unity Catalog function — identify alternate inventory',
    category: 'tool',
    color: 'rgba(168, 85, 247, 0.15)',
    borderColor: '#a855f7',
  },
  {
    id: 'get_supplier_details',
    label: 'get_supplier_details',
    description: 'Unity Catalog function — supplier information',
    category: 'tool',
    color: 'rgba(168, 85, 247, 0.15)',
    borderColor: '#a855f7',
  },
  {
    id: 'temp_gap',
    label: 'temp_gap',
    description: 'Unity Catalog function — temperature gap calculation',
    category: 'tool',
    color: 'rgba(168, 85, 247, 0.15)',
    borderColor: '#a855f7',
  },
  {
    id: 'search_supplier_sops',
    label: 'search_supplier_sops',
    description: 'Vector Search — find relevant supplier SOPs',
    category: 'tool',
    color: 'rgba(236, 72, 153, 0.15)',
    borderColor: '#ec4899',
  },
  {
    id: 'send_email',
    label: 'send_email',
    description: 'Mailgun API — send styled HTML emails',
    category: 'tool',
    color: 'rgba(34, 197, 94, 0.15)',
    borderColor: '#22c55e',
  },
  {
    id: 'send_sms',
    label: 'send_sms',
    description: 'Twilio API — send SMS text messages',
    category: 'tool',
    color: 'rgba(34, 197, 94, 0.15)',
    borderColor: '#22c55e',
  },
];

const connections: FlowConnection[] = [
  { from: 'user', to: 'orchestrator', label: 'User query' },
  { from: 'orchestrator', to: 'meteorologist', label: '' },
  { from: 'orchestrator', to: 'sql-analyst', label: '' },
  { from: 'orchestrator', to: 'supplier', label: '' },
  { from: 'orchestrator', to: 'research', label: '' },
  { from: 'orchestrator', to: 'email', label: '' },
  { from: 'orchestrator', to: 'sms', label: '' },
  { from: 'meteorologist', to: 'check_weather', label: '' },
  { from: 'sql-analyst', to: 'get_shipments', label: '' },
  { from: 'sql-analyst', to: 'get_backup_inventory', label: '' },
  { from: 'sql-analyst', to: 'temp_gap', label: '' },
  { from: 'supplier', to: 'get_supplier_details', label: '' },
  { from: 'supplier', to: 'search_supplier_sops', label: '' },
  { from: 'email', to: 'send_email', label: '' },
  { from: 'sms', to: 'send_sms', label: '' },
];

function NodeCard({
  node,
  step,
  onClick,
  isSelected,
}: {
  node: AgentNode;
  step?: number;
  onClick: () => void;
  isSelected: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 rounded-lg border-2 px-3 py-2 text-left transition-all duration-200 hover:scale-105 cursor-pointer min-w-0"
      style={{
        backgroundColor: node.color,
        borderColor: isSelected ? node.borderColor : `${node.borderColor}66`,
        boxShadow: isSelected ? `0 0 12px ${node.borderColor}44` : 'none',
      }}
    >
      <div className="min-w-0">
        <div className="text-xs font-semibold text-foreground truncate">
          {node.label}
        </div>
        {step !== undefined && (
          <div className="text-[10px]" style={{ color: node.borderColor }}>
            Step {step} of 6
          </div>
        )}
      </div>
    </button>
  );
}

function ToolChip({
  node,
  onClick,
  isSelected,
}: {
  node: AgentNode;
  onClick: () => void;
  isSelected: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-md border px-2.5 py-1.5 text-[11px] font-mono transition-all duration-200 hover:scale-105 cursor-pointer"
      style={{
        backgroundColor: node.color,
        borderColor: isSelected ? node.borderColor : `${node.borderColor}66`,
        color: node.borderColor,
        boxShadow: isSelected ? `0 0 8px ${node.borderColor}33` : 'none',
      }}
    >
      {node.label}
    </button>
  );
}

const legendItems = [
  { label: 'Orchestrator', color: '#eab308' },
  { label: 'Sub-Agent', color: '#3b82f6' },
  { label: 'Custom Tool', color: '#22c55e' },
  { label: 'UC Function', color: '#a855f7' },
  { label: 'Vector Search', color: '#ec4899' },
];

export function AgentFlowModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<AgentNode | null>(null);

  if (!open) return null;

  const agentList = agents.filter((a) => a.id !== 'orchestrator');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* overlay */}
      <div
        className="absolute inset-0 bg-black/80 animate-in fade-in-0"
        onClick={onClose}
      />

      {/* modal */}
      <div className="relative z-10 w-[90vw] max-w-4xl max-h-[85vh] overflow-y-auto rounded-xl border bg-background shadow-2xl animate-in fade-in-0 zoom-in-95">
        {/* header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-background px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold">WeatherWise Agent Flow</span>
            <span className="rounded-full bg-primary/10 px-3 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
              Multi-Agent Pipeline
            </span>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <XIcon className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-6 py-2">
          <p className="text-xs text-muted-foreground">
            Click any component to explore its details
          </p>
        </div>

        {/* flow diagram */}
        <div className="px-6 pb-4">
          <div className="rounded-lg border border-border/50 bg-muted/30 p-6">
            {/* Row 1: User → Orchestrator */}
            <div className="flex items-center justify-center gap-4 mb-6">
              <div className="flex items-center gap-2 rounded-lg border-2 border-muted-foreground/30 bg-muted/50 px-4 py-2">
                <span className="text-xl">👤</span>
                <span className="text-xs font-semibold">User Query</span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                <span className="text-xs">───</span>
                <span className="text-[10px] rounded bg-muted px-1.5 py-0.5">
                  natural language
                </span>
                <span className="text-xs">→</span>
              </div>
              <NodeCard
                node={agents[0]}
                onClick={() => setSelected(agents[0])}
                isSelected={selected?.id === agents[0].id}
              />
            </div>

            {/* Connector line */}
            <div className="flex justify-center mb-4">
              <div className="w-px h-6 bg-border" />
            </div>

            <div className="flex justify-center mb-2">
              <span className="text-[10px] text-muted-foreground rounded bg-muted px-2 py-0.5">
                routes to specialized sub-agents
              </span>
            </div>

            <div className="flex justify-center mb-4">
              <div className="w-px h-4 bg-border" />
            </div>

            {/* Row 2: Sub-agents grid */}
            <div className="grid grid-cols-3 gap-3 mb-6">
              {agentList.map((agent, i) => (
                <NodeCard
                  key={agent.id}
                  node={agent}
                  step={i + 1}
                  onClick={() => setSelected(agent)}
                  isSelected={selected?.id === agent.id}
                />
              ))}
            </div>

            {/* Connector */}
            <div className="flex justify-center mb-2">
              <div className="w-px h-4 bg-border" />
            </div>
            <div className="flex justify-center mb-2">
              <span className="text-[10px] text-muted-foreground rounded bg-muted px-2 py-0.5">
                invokes tools
              </span>
            </div>
            <div className="flex justify-center mb-4">
              <div className="w-px h-4 bg-border" />
            </div>

            {/* Row 3: Tools */}
            <div className="flex flex-wrap justify-center gap-2">
              {tools.map((tool) => (
                <ToolChip
                  key={tool.id}
                  node={tool}
                  onClick={() => setSelected(tool)}
                  isSelected={selected?.id === tool.id}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="mx-6 mb-4 rounded-lg border p-4 animate-in fade-in-0 slide-in-from-bottom-2">
            <div className="flex items-center gap-2 mb-1">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: selected.borderColor }}
              />
              <span className="text-sm font-semibold">{selected.label}</span>
              <span
                className="text-[10px] uppercase tracking-wider font-medium"
                style={{ color: selected.borderColor }}
              >
                {selected.category}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {selected.description}
            </p>
            {selected.category === 'agent' || selected.id === 'orchestrator' ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="text-[10px] text-muted-foreground mr-1">
                  Uses:
                </span>
                {connections
                  .filter((c) => c.from === selected.id)
                  .map((c) => {
                    const target = [...agents, ...tools].find(
                      (n) => n.id === c.to,
                    );
                    return target ? (
                      <button
                        key={c.to}
                        onClick={() => setSelected(target)}
                        className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono hover:bg-muted-foreground/20 cursor-pointer transition-colors"
                        style={{ color: target.borderColor }}
                      >
                        {target.label}
                      </button>
                    ) : null;
                  })}
              </div>
            ) : null}
          </div>
        )}

        {/* Legend */}
        <div className="border-t px-6 py-3 flex items-center gap-4 flex-wrap">
          {legendItems.map((item) => (
            <div key={item.label} className="flex items-center gap-1.5">
              <div
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-[10px] text-muted-foreground">
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
