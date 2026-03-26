# bx3_app_ui — Build the bobertx3 App UI

Build or customize the React frontend for a bobertx3 Databricks App. This covers the full UI pattern: navigation tabs, Agent Flow modal, Dashboard page, Genie page, custom tool renderers, greeting page, and design system.

## Usage

`/bx3_app_ui <action>`

Actions:
- `/bx3_app_ui full` — Build complete UI from scratch
- `/bx3_app_ui agent-flow` — Create/update the Agent Flow modal
- `/bx3_app_ui dashboard` — Create/update the Dashboard page
- `/bx3_app_ui tool-renderers` — Create/update custom tool renderers
- `/bx3_app_ui greeting` — Create/update the greeting/landing page
- `/bx3_app_ui follow-ups` — Create/update context-aware follow-up suggestions

---

## Tech Stack

```
React 18 + Vite + TypeScript
TailwindCSS v4 + @tailwindcss/typography
shadcn/ui components (Radix UI primitives)
Framer Motion (micro-animations)
Vercel AI SDK (useChat hook, streaming)
react-router-dom v6 (page routing)
Geist + Geist Mono fonts (Google Fonts)
```

---

## Navigation — Always Three+ Tabs

The `chat-header.tsx` component ALWAYS includes a compact tab bar:

| Tab | Route | Purpose |
|-----|-------|---------|
| **Agent** | `/` or `/chat/:id` | Primary chat interface |
| **Dashboard** | `/dashboard` | Data visualization for the domain |
| **Ask Genie** | `/genie` | Genie Space natural-language SQL |

Plus an **"Agent Flow"** button on the right side that opens the architecture modal.

Active tab styling: `bg-primary/10 text-primary` with rounded corners.

### Header Component Pattern

```tsx
const navItems = [
  { label: "Agent", path: "/", matchPaths: ["/", "/chat"] },
  { label: "Dashboard", path: "/dashboard", matchPaths: ["/dashboard"] },
  { label: "Ask Genie", path: "/genie", matchPaths: ["/genie"] },
];

// Right side: Agent Flow button
<Button variant="ghost" size="sm" onClick={() => setShowAgentFlow(true)}>
  Agent Flow
</Button>
```

---

## Agent Flow Modal (REQUIRED)

Every project MUST have `agent-flow-modal.tsx`. This is an interactive, click-explorable visualization of the agent architecture.

### Data Structure

```tsx
interface AgentNode {
  id: string;
  name: string;
  type: "orchestrator" | "sub-agent" | "custom-tool" | "uc-function" | "vector-search";
  description: string;
  connections?: string[];  // IDs of connected nodes
}

interface FlowConnection {
  from: string;
  to: string;
  label?: string;
}
```

### Layout Structure

```
Row 1: [User Query] ──────► [Main Orchestrator]
                                    │
Row 2:     ┌────────────┬──────────┼──────────┬────────────┐
           │            │          │          │            │
      [Sub-Agent 1] [Sub-Agent 2] ... [Sub-Agent N]
                                    │
Row 3:     ┌────────────┬──────────┼──────────┬────────────┐
           │            │          │          │            │
      [Tool 1]     [Tool 2]    [Tool 3]   [Tool N]
```

### Color Coding (MUST follow exactly)

| Category | Background | Border | Text |
|----------|------------|--------|------|
| Orchestrator | `rgba(234, 179, 8, 0.15)` | `#eab308` | `#eab308` |
| Sub-Agent | `rgba(59, 130, 246, 0.15)` | `#3b82f6` | `#3b82f6` |
| Custom Tool | `rgba(34, 197, 94, 0.15)` | `#22c55e` | `#22c55e` |
| UC Function | `rgba(168, 85, 247, 0.15)` | `#a855f7` | `#a855f7` |
| Vector Search | `rgba(236, 72, 153, 0.15)` | `#ec4899` | `#ec4899` |

### Modal Features

- Full-screen overlay with backdrop blur
- Sticky header with title + close button
- Scrollable content area with max-height
- **Clickable nodes** with hover scale effect (`transform: scale(1.02)`)
- **Detail panel** on the right showing selected node's:
  - Name and type badge
  - Description paragraph
  - Connected tools/agents list
- **Legend** at bottom explaining color categories
- Close on Escape key or backdrop click

### Implementation Pattern

```tsx
const AgentFlowModal = ({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) => {
  const [selectedNode, setSelectedNode] = useState<AgentNode | null>(null);

  const agents: AgentNode[] = [
    // Hardcoded array — populate per project
  ];

  const tools: AgentNode[] = [
    // Hardcoded array — populate per project
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm">
          <motion.div className="mx-auto max-w-5xl bg-background rounded-xl shadow-2xl">
            {/* Orchestrator row */}
            {/* Sub-agents grid (3-column) */}
            {/* Tools grid (color-coded by type) */}
            {/* Detail panel (conditionally rendered) */}
            {/* Legend */}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
```

---

## Dashboard Page

A dedicated data visualization page at `/dashboard`.

### Architecture

```
DashboardPage.tsx
  ├── fetches GET /api/dashboard/summary
  ├── StatusCards (KPI row at top)
  ├── Primary data table (full width)
  └── Secondary grids (2-column layout)
```

### Server Route (`routes/dashboard.ts`)

```typescript
router.get("/summary", requireAuth, async (req, res) => {
  const warehouseId = process.env.DATABRICKS_SQL_WAREHOUSE_ID;
  // Execute SQL queries against UC tables
  const shipments = await executeSql(warehouseId, `SELECT * FROM ${catalog}.${schema}.shipments`);
  const suppliers = await executeSql(warehouseId, `SELECT * FROM ${catalog}.${schema}.suppliers`);
  const inventory = await executeSql(warehouseId, `SELECT * FROM ${catalog}.${schema}.inventory`);
  // Compute status counts server-side
  res.json({ shipments, suppliers, inventory, statusCounts });
});
```

### Dashboard Components Pattern

**StatusCards** — Top row, 4 KPI cards:
- Responsive: 2 cols on mobile, 4 on desktop
- Each card: icon, count, label, colored indicator
- Status colors consistent with data table badges

**Primary Data Table** — Full entity table:
- Sortable columns
- Status badges with color coding
- Red background tint for critical rows (e.g., delayed)
- ID columns in `font-mono`
- Date columns formatted

**Secondary Grids** — 2-column grid:
- Inventory overview (by location)
- Supplier overview (by tier)
- Low-stock highlighting (threshold-based red styling)
- Tier badges: Tier-1=green, Tier-2=yellow, Tier-3=red

---

## Genie Page

A natural-language SQL Q&A interface at `/genie`.

### Flow

1. User sends question → `POST /api/genie/start-conversation`
2. Follow-ups → `POST /api/genie/conversations/:id/messages`
3. Poll status → `GET /api/genie/conversations/:id/messages/:messageId` (2s intervals)
4. Get results → `GET /api/genie/conversations/:id/messages/:messageId/query-result`

### UI Pattern

- Sample questions grid on initial load (4-6 domain-specific questions)
- User messages right-aligned in blue bubbles
- Genie responses left-aligned with:
  - Narrative text (markdown rendered)
  - Collapsible SQL query section
  - Result table with columns from manifest schema
- Loading spinner: "Genie is thinking..."
- Context-aware follow-up suggestions after each response

---

## Custom Tool Renderers

Create rich React components for each tool's output instead of showing raw JSON.

### Registry Pattern (`tool-renderers/index.tsx`)

```tsx
export function renderToolOutput(toolName: string, output: any): React.ReactNode | null {
  // Normalize tool name (handle UC qualified names like catalog__schema__tool_name)
  const normalizedName = toolName.includes("__")
    ? toolName.split("__").pop()!
    : toolName;

  switch (normalizedName) {
    case "get_shipments":
      return <ShipmentTable data={parseToolOutput(output)} />;
    case "get_supplier_details":
      return <SupplierCards data={parseToolOutput(output)} />;
    case "check_weather":
      return <WeatherCard data={parseToolOutput(output)} />;
    case "get_backup_inventory":
      return <InventoryTable data={parseToolOutput(output)} />;
    default:
      return null;  // Falls back to raw JSON display
  }
}
```

### Renderer Guidelines

- **Tables** for list/query results (shipments, inventory)
- **Cards** for entity details (suppliers, weather)
- **Grid layout** for multiple items (2 columns on mobile)
- **Status badges** with consistent color coding
- **Low-stock highlighting** with threshold-based red styling
- **Graceful null handling** — never crash on missing fields
- **Responsive** — overflow-x on tables, stack on mobile

### Weather Card Pattern

```tsx
const WeatherCard = ({ data }: { data: WeatherData }) => {
  const weatherEmoji = getWeatherEmoji(data.weather_code);
  return (
    <div className="rounded-lg border p-4 inline-flex gap-4 items-center">
      <span className="text-3xl">{weatherEmoji}</span>
      <div>
        <div className="text-2xl font-bold">{data.temperature}°F</div>
        <div className="text-sm text-muted-foreground">{data.conditions}</div>
        <div className="text-xs text-muted-foreground">Wind: {data.wind_speed} mph</div>
      </div>
    </div>
  );
};
```

---

## Greeting / Landing Page

The `NewChatPage` shows an animated greeting when no chat is active.

### Pattern

```tsx
const Greeting = () => (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
    <AnimationAssistantIcon size="lg" />
    <h1 className="text-2xl font-semibold">Hello there! I'm the [Agent Name].</h1>
    <p className="text-muted-foreground">[Domain-specific description]</p>
  </motion.div>
);
```

### Suggested Actions

4 domain-specific starter prompts in a 2x2 grid:
- Staggered fade-in animations (0.5s, 0.6s delays)
- Each prompt is a clickable card
- Text shows a realistic question the agent can answer
- Clicking sends the prompt as a user message

---

## Follow-Up Actions

Context-aware suggested follow-ups based on the agent's last response.

### Pattern (`follow-up-actions.tsx`)

```tsx
const getFollowUps = (lastMessage: string): string[] => {
  const lower = lastMessage.toLowerCase();

  if (lower.includes("at_risk") || lower.includes("borderline")) {
    return [
      "What are the supplier SOP details for this shipment?",
      "Draft an alert email to the escalation contact",
      "Is there backup inventory available nearby?",
    ];
  }
  if (lower.includes("shipment") || lower.includes("shp-")) {
    return [
      "Check the weather at the destination",
      "Look up the supplier contact details",
      "Find backup inventory options",
    ];
  }
  // ... more keyword → suggestion mappings
  return [];
};
```

- Render as horizontal chip buttons below the last assistant message
- Max 3 suggestions
- Clicking sends the suggestion as a user message

---

## Animated Assistant Icon

Gradient circles with pulse animation:
- Colors: `#4299E0 → #CA42E0 → #FF5F46`
- Pulse: scale 0.9 → 1.1 during loading
- Rotating gradient: 1800° over 2s
- Smooth return to resting state

---

## Design System

### CSS Variables (index.css)

```css
:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --primary: 240 5.9% 10%;
  --muted: 240 4.8% 95.9%;
  --border: 240 5.9% 90%;
  --radius: 0.5rem;
}

.dark {
  --background: 240 10% 3.9%;
  --foreground: 0 0% 98%;
  /* ... inverted */
}
```

### Consistent Colors

| Use | Color |
|-----|-------|
| User messages | `#006cff` |
| Primary actions | `#3b82f6` |
| Success / Tier-1 | `#22c55e` |
| Danger / Delayed | `#ef4444` |
| Warning / Orchestrator | `#eab308` |
| Muted text | `#6b7280` |

### Typography

- **Fonts**: Geist (sans), Geist Mono (code)
- **Headings**: `text-2xl font-semibold` (greeting), `text-xl font-semibold` (section)
- **Body**: `text-sm` (chat), `text-xs` (tables, metadata)
- **Code/IDs**: `font-mono text-xs`

### Component Library

Use shadcn/ui: Button, Input, Textarea, Badge, Tooltip, Sheet, Sidebar, Collapsible, Dropdown, AlertDialog.

### Animations

- **Framer Motion** for: message enter/exit, modal open/close, greeting fade-in
- **CSS transitions** for: hover states, color changes
- **Staggered delays** for: suggested actions, greeting text lines

---

## Chat Features Checklist

When building the UI, ensure these features are present:
- [ ] Sidebar with chat history (collapsible)
- [ ] Streaming responses with typing indicator
- [ ] Tool call visualization (expandable, shows args + result)
- [ ] Custom tool renderers (cards/tables, not raw JSON)
- [ ] Follow-up action suggestions
- [ ] Agent Flow modal (interactive architecture diagram)
- [ ] Dashboard page with KPIs + data tables
- [ ] Genie page with SQL Q&A
- [ ] Greeting page with suggested prompts
- [ ] Dark/light theme support
- [ ] Multimodal input (text + file upload)
- [ ] Message actions (copy)
- [ ] Session-based auth via Databricks OAuth
