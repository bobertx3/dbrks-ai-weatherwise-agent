---
# ── Page fields (UC semantics · Pages · POST /api/2.0/knowledge/pages) ──
display_name: Cold-Chain Shipment Risk
domain: domains/b530da5f-dc5d-4833-909d-e3971e0e76bb   # Supply Chain
owner:                              # blank = the caller. Otherwise a decimal principal ID
state: DRAFT                        # DRAFT or PUBLISHED (publishing needs MANAGE PAGES)
synonyms:
  - At-risk shipments
  - Weather risk
  - Cold chain risk
  - Temperature excursion
  - Heat risk
  - Shipment escalation
description: >-
  Whether an active MedTech cold-chain shipment is at risk from destination
  weather (forecast high above its max allowed temperature) or has already
  broken its temperature range, and how risk is prioritized for escalation.

# ── Asset links (POST /api/2.0/knowledge/pages/{id}/asset-link-categories/{SOURCE|RELATED_ASSETS}/asset-links) ──
related_assets:
  - __CATALOG__.__SCHEMA__.shipment_risk_metrics
  - __CATALOG__.__SCHEMA__.shipments
  - __CATALOG__.__SCHEMA__.weather_forecast
  - __CATALOG__.__SCHEMA__.inventory
sources:
  - __CATALOG__.__SCHEMA__.shipments
  - __CATALOG__.__SCHEMA__.weather_forecast
  - __CATALOG__.__SCHEMA__.suppliers
  - __CATALOG__.__SCHEMA__.supplier_sops
---

## Definition

In the WeatherWise supply-chain semantic layer, **cold-chain shipment risk** measures how likely it is that a temperature-controlled MedTech shipment (implants, valves and similar devices) arrives **out of spec**. Each shipment carries its own allowed range, from `temperature_min_f` to `temperature_max_f`. For implants and valves the range is **36–46 °F (2–8 °C)**.

There are two kinds of risk:

- **Weather at-risk**: an **active** shipment (any status except `Delivered`) where tomorrow's **forecast high** in the destination city is **above the shipment's `temperature_max_f`**. This is the default meaning of "at risk".
- **Temperature excursion**: the shipment's **last recorded payload temperature** is already outside its allowed range. The breach has already happened, whatever the forecast says.

Risk is graded with a **Weather Risk Band**:

- **Severe**: the forecast high is **15 °F or more** above the max
- **Elevated**: the forecast high is **1–14 °F** above the max
- **Cold Exposure**: the forecast low is below the min
- **Within Range**: the forecast stays inside the allowed range

Risk is always compared against **the shipment's own threshold**. Do not use a fixed number. Do not use the city-level `degrees_above_cold_chain_max` column for shipment-level risk. Forecasts are **next-day only**.

## Business use

Cold-chain shipment risk tells operations teams which shipments to act on **before** weather causes spoilage, a cancelled procedure or a compliance deviation.

Common business uses include:

- finding **which in-transit shipments into a metro are at risk** from tomorrow's heat
- putting **STAT** shipments first. These are procedure-critical, so they get email and SMS escalation and a backup-inventory search
- flagging **procedures at risk**: at-risk shipments that arrive within 1 day of the scheduled `procedure_date`, which leaves no time to re-ship
- following the supplier's **escalation SOP**. **Tier 1** covers a delay under 24 h. **Tier 2** covers a payload above 8 °C (46 °F) or a delay over 24 h. **Tier 3** is critical. Contacts and SLAs come from the SOP, never from assumptions
- sourcing **backup inventory** with the same `sku`, `on_hand_qty > 0` and a `lot_expiry` after the procedure date
- tracking **carrier and supplier performance** through excursion and delay rates

Supplier tier (`Tier-1`, `Tier-2`) is a commercial classification. It is **not** the same as an SOP escalation tier.

## Examples

Examples of governed measures in `shipment_risk_metrics` include:

- **Weather At-Risk Shipments**: active shipments whose destination forecast high is above `temperature_max_f`
- **STAT At-Risk Shipments**: weather at-risk shipments with `priority = 'STAT'`
- **Procedures at Risk**: weather at-risk shipments where `DATEDIFF(procedure_date, eta_date) <= 1`
- **Weather Risk Rate**: Weather At-Risk Shipments ÷ Active Shipments
- **Temperature Excursions** / **Excursion Rate**: shipments whose last recorded temperature is outside the allowed range, as a count and as a share of all shipments
- **Avg Forecast Temp Gap F**: the average of `forecast high − temperature_max_f`. It uses the same logic as the `temp_gap` UC function
- **Delayed Shipments**, **Delay Rate** and **Avg Delay Hours**: delay KPIs. Avg Delay Hours excludes shipments with no delay

In the semantic layer, business terms such as **heat risk**, **shipments at risk** and **cold chain breach** map to these measures. For example, "How many STAT shipments into New York are at risk tomorrow?" becomes ``MEASURE(`STAT At-Risk Shipments`)`` filtered to `Destination = 'New York, NY'`.
