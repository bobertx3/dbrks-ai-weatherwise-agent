# 🌦 MedTech Supply Chain Agent — Weather-Aware Escalation Agent

The **Weather-Aware Supply Chain Agent** answers operational supply-chain questions using real data, predictive reasoning, and automated actions.  
It brings together structured logistics data, live weather feeds, and supplier escalation procedures to help MedTech operations teams act before issues occur.

---

## 📘 Overview
The **Weather-Aware Supply Chain Agent** monitors and mitigates weather-related risks across the MedTech logistics network.  
It ensures **temperature-sensitive and time-critical medical products** are delivered safely and on time by analyzing structured and unstructured data, checking for extreme weather, and automating supplier escalation workflows.

---

## 🎯 Goal
Proactively detect and resolve **shipment disruptions** caused by weather events — including heatwaves, blizzards, storms, or floods — before they impact patient care or regulatory compliance.

---

## 💬 Example Questions Users Can Ask

| Category | Example Prompt |
|-----------|----------------|
| **Weather Risk & Escalation** | “Temperatures in New York City are expected to hit 105°F — which shipments are at risk and who should I escalate to?” |
| **Delivery Status** | “Show me what medical implant shipments were delivered this week and any that were delayed.” |
| **Supplier Policies** | “If a Zimmer Biotech shipment is delayed due to weather, what’s the escalation procedure?” |

---

## 🧠 Agent Workflow

1. **Shipment Check** — Retrieve carrier, ETA, and temperature logs from Unity Catalog.  
2. **Weather Check** — Detect regional threats such as heatwaves, snowstorms, or heavy rain along the route or destination.  
3. **Inventory Check** — Locate alternate stock or suppliers near affected delivery zones.  
4. **SOP Retrieval (RAG)** — Search supplier escalation policies or PDF SOPs to determine next steps.  
5. **Summarize & Act** — Generate a concise risk report and, if needed, send an **email alert** to logistics and supplier contacts.

---

## ⚙️ Tools

| Tool | Description |
|------|--------------|
| `get_shipment` | Retrieve shipment and temperature details from UC tables. |
| `check_weather` | Detect extreme weather and forecast disruptions. |
| `get_inventory_near` | Find alternate stock or supplier sites near the impacted region. |
| `vector_search_tool('supplier_policies_index')` | Retrieve escalation SOPs and SLAs from embedded text or PDFs. |
| `send_email` | Send formatted alerts or escalation summaries automatically. |

---

## 💡 Business Value

### 🌍 Operational Impact
- **Reduces weather-related disruption response time** from hours to seconds.  
- Provides unified visibility across **shipments, weather forecasts, and supplier status**.  
- Automates **escalation and compliance workflows** under adverse conditions.

### 💰 Cost & Efficiency
- **Prevents spoilage and stockouts** for high-value implants or biologics.  
- **Avoids SLA penalties** by triggering proactive mitigation.  
- Boosts **team productivity** through agent-guided decision support.

### 🛡️ Risk & Compliance
- Maintains **traceability** and **audit readiness** for regulated logistics.  
- Enforces **validated SOPs** and supplier escalation policies.  
- Enhances **patient safety** by ensuring timely delivery and product integrity.

---

## 🧩 Example Data Sources

| File | Purpose |
|------|----------|
| `shipments.csv` | Shipment records, routes, ETA, carrier, and temperature logs. |
| `suppliers.csv` | Supplier contacts and escalation policy references. |
| `inventory.csv` | Warehouse and alternate stock data for substitution. |
| `medtech_sops.csv` | Product and escalation documents used for RAG or vector search. |

---

## 🚀 Example Demo Flow

1. **Setup Data**  
   Load all CSVs into Delta tables and register Unity Catalog functions:
   - `get_shipment`
   - `get_inventory_near`
   - `get_supplier`
   - `medtech_sops.csv`

2. **Build Agent**  
   - Create UC tools + custom tools (`check_weather`, `send_email`).  
   - Create vector search index to search SOPs.  
   - Configure the system prompt with weather-risk reasoning.

3. **Test Agent**
   - `agent.predict()` → sanity check agent is using all the tools created. 

4. **Evaluate, Register, Deploy**
   - `agent.eval()` → evalution agent against sample or synethic data using LLM judgets.  
   - `mlflow.register_model()` → add to Model Registry.  
   - `agents.deploy()` → enable live inference and human-review app for feedback from business SMEs.

---

## 🗂️ Repository Structure

```
/src
 ├── tools/
 │    ├── tool_uc_functions.ipython    # Query structured data
 │    ├── tool_uc_vector_index.ipython # Create vector index
 │    ├── tool_check_weather.py        # Weather API integration
 │    ├── tool_send_email.py           # Send email alerts
 │    ├── __init__.py                  # Python file to ensure tools can be imported as packages 
 ├── supply_chain_agent.py             # LangGraph + MLflow logic
 ├── data/
 |    ├── shipments.csv                   
 |    ├── suppliers.csv                
 |    ├── inventory.csv                   
 |    ├── medtech_supplier_sops.csv        
 ├── setup.ipython                     # loads /data into Delta Tables and creates Vector Endpoint   
 ├── config.py                         # demo config such as catalog, schema 
 └── README.md
```

---

© 2025 Databricks / MedTech Demo  |  Author: *Robert “Bobby” Leach*
