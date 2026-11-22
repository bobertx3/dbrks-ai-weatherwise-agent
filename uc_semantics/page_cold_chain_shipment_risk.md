---
# ── Page fields (UC semantics · Pages · POST /api/2.0/knowledge/pages) ──
display_name: Temperature-Controlled Shipment Risk
domain: domains/b530da5f-dc5d-4833-909d-e3971e0e76bb   # Supply Chain
owner:                              # blank = the caller. Otherwise a decimal principal ID
state: DRAFT                        # DRAFT or PUBLISHED (publishing needs MANAGE PAGES)
synonyms:
  - At-risk shipments
  - Cold chain risk
  - Temperature-controlled shipment risk
  - Temperature excursion
  - Surgery at risk
  - Shipment escalation
description: >-
  Whether an active temperature-controlled MedTech shipment has already broken its
  temperature range or will arrive after its scheduled procedure, and how risk
  is prioritized for escalation. Weather risk is computed live by the agent.

# ── Asset links (POST /api/2.0/knowledge/pages/{id}/asset-link-categories/{SOURCE|RELATED_ASSETS}/asset-links) ──
related_assets:
  - __CATALOG__.__SCHEMA__.shipment_risk_metrics
  - __CATALOG__.__SCHEMA__.shipments
  - __CATALOG__.__SCHEMA__.inventory
sources:
  - __CATALOG__.__SCHEMA__.shipments
  - __CATALOG__.__SCHEMA__.suppliers
  - __CATALOG__.__SCHEMA__.supplier_sops
---

## Definition

In the WeatherWise supply-chain semantic layer, **temperature-controlled shipment risk** measures how likely it is that a temperature-controlled MedTech shipment arrives **out of spec**. Each shipment carries its own allowed range, from `temperature_min_f` to `temperature_max_f`, and the ranges differ by product:

- **Frozen** products stay below freezing: fibrin sealant **-22 to -4 °F** (-30 to -20 °C) and cryopreserved bone allograft **-112 to -40 °F**. A breach is warming or thawing.
- **Refrigerated** products stay at **36–46 °F (2–8 °C)**: thrombin hemostat and corneal grafts. A breach is freezing or warming.
- **Room-temperature tissue valves** stay at **50–77 °F (10–25 °C)** and must never freeze. A breach is freezing (below 32 °F) or heat.
- **Coated stents** (**59–77 °F**) and **drug-coated balloons** (**59–86 °F**) are heat-sensitive. A breach is heat.

Risk in the data has two governed definitions:

- **Temperature excursion**: the shipment's **last recorded payload temperature** is already outside its own allowed range, above `temperature_max_f` or below `temperature_min_f`. The breach has already happened.
- **Procedure (surgery) at risk**: an **active** shipment (any status except `Delivered`) whose `eta_date` is **after** its `procedure_date`.

**Weather risk is not stored.** The WeatherWise agent checks the **live** destination forecast (`check_weather`) and computes the gap to the shipment's own `temperature_max_f` with the `temp_gap` UC function: **AT_RISK** ≥ 20 °F over, **BORDERLINE** 10–19 °F, **NOT_AT_RISK** < 10 °F.

Risk is always compared against **the shipment's own threshold**. Do not use a fixed number. The weather gap is a heat-only check: for frozen and freeze-sensitive products, rely on the excursion rule and the product's SOP instead.

## Business use

Temperature-controlled shipment risk tells operations teams which shipments to act on **before** a temperature breach or delay causes spoilage, a cancelled procedure or a compliance deviation.

Common business uses include:

- finding **which in-transit shipments into a metro** are delayed, out of spec, or late for surgery (then asking the agent about live weather)
- putting **STAT** shipments first. These are procedure-critical, so they get email and SMS escalation and a backup-inventory search
- flagging **procedures at risk**: active shipments whose ETA is after the scheduled `procedure_date`
- following the product's **escalation SOP** (`supplier_sops`). Triggers are product-specific. For example, any freeze of a tissue valve means quarantine, and any thaw of a frozen sealant means QA escalation. Contacts and SLAs come from the SOP, never from assumptions
- sourcing **backup inventory** with the same `sku`, `on_hand_qty > 0` and a `lot_expiry` after the procedure date
- tracking **carrier and supplier performance** through excursion and delay rates

Supplier tier (`Tier-1`, `Tier-2`) is a commercial classification. It is **not** the same as an SOP escalation tier.

## Examples

Examples of governed measures in `shipment_risk_metrics` include:

- **Procedures at Risk**: active shipments where `eta_date > procedure_date`
- **STAT Procedures at Risk**: procedures at risk with `priority = 'STAT'`
- **Temperature Excursions** / **Excursion Rate**: shipments whose last recorded temperature is outside the allowed range, as a count and as a share of all shipments
- **Delayed Shipments**, **Delay Rate** and **Avg Delay Hours**: delay KPIs. Avg Delay Hours excludes shipments with no delay

In the semantic layer, business terms such as **surgeries at risk**, **out of spec** and **temperature breach** map to these measures. For example, "How many STAT shipments into New York will miss their surgery?" becomes ``MEASURE(`STAT Procedures at Risk`)`` filtered to `Destination = 'New York, NY'`.
