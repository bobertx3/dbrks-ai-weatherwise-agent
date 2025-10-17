## 🌦 MedTech - WeatherWise Supply Chain Escalation Agent

The **WeatherWise Supply Chain Escalation Agent** helps MedTech operations teams **anticipate and mitigate weather-related shipment risks** using live data, predictive reasoning, and automated escalation workflows.

---

### 🎯 Mission
Detect and resolve **shipment disruptions** before they impact **patients, compliance, or cost**.

---

### 🎯 Scenario

Business Process
![](img/manual_flow.png)

Agent Flow
![](img/agent_flow.png)
---

### 💬 Example Queries

| Category | Example |
|-----------|----------|
| **Full Automation** | “The weather in New York will be hot tomorrow. Which in-transit shipments are at risk, what escalation steps should I take, and is there a backup supplier nearby? Email me a report and send an SMS summary.” |
| **Weather Risks** | “Which shipments are at risk due to high temperatures in NYC?” |
| **Delivery Status** | “Show in-transit implant shipments for this week.” |
| **Supplier SOPs** | “What’s Zimmer’s escalation process for temperature exceptions?” |

---

### 💡 Business Value

#### ⚡ Speed
- **Hours → seconds** for risk detection  
- Automated **weather + shipment correlation**  
- One-click **escalation and notification**

#### 💰 Savings
- Avoids **spoilage, delays, and SLA fines**  
- Reduces **manual triage workload**  
- Maximizes **on-time, in-spec delivery**

#### 🛡️ Compliance
- Follows **supplier SOPs automatically**  
- Provides **audit-ready traceability**  
- Strengthens **patient safety assurance**

---

### 🧠 Escalation Crew — Agents and Tools

#### 🌦 METEOROLOGIST  
**Role:** Weather and risk analyst  
**Goal:** Analyze forecast data and compute temperature gaps between ambient and shipment thresholds  
**Tools:** `check_weather`, `temp_gap`

---

#### 📊 SQL ANALYST  
**Role:** Data analyst focused on MedTech shipment logistics  
**Goal:** Retrieve shipments (optionally filtered by destination and/or status) and expose the maximum allowable temperatures needed for risk evaluation  
**Tools:** `get_shipments`, `get_backup_inventory`

---

#### 📁 SUPPLIER RESEARCHER  
**Role:** Knowledge analyst specializing in supplier compliance and escalation workflows  
**Goal:** Identify supplier-specific SOPs, escalation contacts, and nearby backup inventory  
**Tools:** `get_supplier_details`, `search_supplier_sops`

---

#### 📝 EMAIL COPYWRITER  
**Role:** Communications agent for detailed escalation summaries  
**Goal:** Compose and send email reports summarizing affected shipments and next steps  
**Tools:** `send_email` (via any email service API)

---

#### 📱 TEXTER  
**Role:** Rapid notifier for short alerts  
**Goal:** Send SMS notifications to field or operations teams for immediate awareness  
**Tools:** `send_sms` (via any SMS service)

---

### ⚙️ Tools Overview

#### 🔹 Unity Catalog Tools
| Tool | Description |
|------|--------------|
| `get_shipments` | Retrieve shipment, carrier, and temperature data |
| `get_backup_inventory` | Identify alternate or nearby stock locations |
| `get_supplier_details` | Retrieve supplier info and escalation contacts |
| `temp_gap` | Calculate ambient vs. threshold temperature differences |
| `search_supplier_sops` | Retrieve escalation SOPs from the **`supplier_sops_vs_index`** vector search index |

#### 🔹 Custom Tools
| Tool | Description |
|------|--------------|
| `check_weather` | Get live or forecasted weather for destination routes |
| `send_email` | Send escalation summaries via **Mailgun** (or any email service API) |
| `send_sms` | Send short alerts via **Twilio SMS** |

---

### 🧩 Demo Data Sources

| File | Description |
|------|--------------|
| `demo_shipments.csv` | Shipment details, ETA, carrier, and temperature logs |
| `demo_suppliers.csv` | Supplier contacts and escalation references |
| `demo_inventory.csv` | Warehouse and backup inventory data |
| `demo_supplier_sops.csv` | Supplier SOPs and escalation documents (for RAG) |

---

© 2025 — *Authored by Bobby Leach*