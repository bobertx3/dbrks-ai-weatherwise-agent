-- ============================================================
-- WeatherWise · Shipment Risk Metric View
-- ============================================================
-- Governed temperature-controlled KPIs for the WeatherWise agent, Genie and
-- AI/BI dashboards. Business definitions live in the companion
-- Genie Ontology page: uc_semantics/page_cold_chain_shipment_risk.md
--
-- __CATALOG__ and __SCHEMA__ are replaced by uc_semantics/deploy.sh
-- using TARGET_CATALOG / TARGET_SCHEMA from _env.
--
-- Requires DBR 17.3+ / current SQL warehouse (synonyms, display_name, format).
-- ============================================================

CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.shipment_risk_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
comment: >-
  Temperature-controlled shipment risk KPIs for temperature-sensitive MedTech shipments (frozen, refrigerated and
  room-temperature products). One row in the source = one shipment, carrying its own temperature_min_f and
  temperature_max_f. Joins the supplier.
  Weather risk is not stored: the WeatherWise agent computes it from live forecasts.
  See the "Temperature-Controlled Shipment Risk" Genie Ontology page for definitions.
source: __CATALOG__.__SCHEMA__.shipments

joins:
  - name: dim_supplier
    source: __CATALOG__.__SCHEMA__.suppliers
    'on': source.supplier_id = dim_supplier.supplier_id

dimensions:
  # ── Shipment ────────────────────────────────────────────────
  - name: Shipment Status
    expr: source.status
    comment: "Lifecycle status: Label-Create, In-Transit, Out-for-Delivery, Delayed, Delivered."
    synonyms: [status, shipment state, delivery status]
  - name: Is Active
    expr: source.status <> 'Delivered'
    comment: "TRUE when the shipment has not yet been delivered."
    synonyms: [active, open shipment, in flight, not delivered]
  - name: Priority
    expr: source.priority
    comment: "Clinical urgency: STAT (procedure-critical, same/next day), Urgent, Routine."
    synonyms: [urgency, clinical priority, stat]
  - name: Carrier
    expr: source.carrier
    synonyms: [shipper, logistics provider, courier]
  - name: Product
    expr: source.product_name
    synonyms: [device, implant, item]
  - name: SKU
    expr: source.sku
  - name: Origin
    expr: source.origin
    synonyms: [ship from, origin city]
  - name: Destination
    expr: source.destination
    comment: "Destination metro in 'City, ST' form, e.g. 'New York, NY'."
    synonyms: [ship to, destination city, metro]
  - name: Delay Reason
    expr: source.delay_reason
    synonyms: [cause of delay, delay cause]
  - name: Ship Date
    expr: source.ship_date
    format:
      type: date
      date_format: year_month_day
  - name: ETA Date
    expr: source.eta_date
    comment: "Current estimated arrival date (may be later than Original ETA Date when delayed)."
    synonyms: [eta, arrival date, expected delivery]
    format:
      type: date
      date_format: year_month_day
  - name: Procedure Date
    expr: source.procedure_date
    comment: "Scheduled surgical procedure that depends on this shipment."
    synonyms: [surgery date, case date, OR date]
    format:
      type: date
      date_format: year_month_day

  # ── Supplier & facility ─────────────────────────────────────
  - name: Supplier
    expr: dim_supplier.supplier_name
    synonyms: [vendor, manufacturer]
  - name: Supplier Tier
    expr: dim_supplier.tier
    synonyms: [vendor tier]
  - name: Facility
    expr: source.destination_facility_name
    synonyms: [hospital, clinic, destination facility]
  - name: Facility Type
    expr: source.destination_facility_type
    comment: "Hospital or Clinic."

measures:
  # ── Volume ──────────────────────────────────────────────────
  - name: Shipments
    expr: COUNT(1)
    comment: "Total shipments."
    synonyms: [shipment count, number of shipments, total shipments]
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Active Shipments
    expr: COUNT(1) FILTER (WHERE source.status <> 'Delivered')
    comment: "Shipments not yet delivered."
    synonyms: [open shipments, in-flight shipments, in transit]
    format: {type: number, decimal_places: {type: exact, places: 0}}

  # ── Delay ───────────────────────────────────────────────────
  - name: Delayed Shipments
    expr: COUNT(1) FILTER (WHERE source.status = 'Delayed')
    synonyms: [late shipments, delays]
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Delay Rate
    expr: MEASURE(`Delayed Shipments`) / NULLIF(MEASURE(`Shipments`), 0)
    comment: "Delayed Shipments / Shipments."
    synonyms: [late rate, percent delayed]
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Avg Delay Hours
    expr: AVG(source.delay_hours) FILTER (WHERE source.delay_hours > 0)
    comment: "Average hours of delay across shipments that are actually delayed (excludes 0)."
    synonyms: [average delay, mean delay]
    format: {type: number, decimal_places: {type: max, places: 1}}

  # ── Temperature integrity ────────────────────────────────────
  - name: Temperature Excursions
    expr: |
      COUNT(1) FILTER (WHERE source.last_recorded_temp_f > source.temperature_max_f
                          OR source.last_recorded_temp_f < source.temperature_min_f)
    comment: "Shipments whose last recorded payload temperature is outside their own range: above temperature_max_f (heat, thaw or warming) or below temperature_min_f (freeze)."
    synonyms: [excursions, out of spec, temp breaches, cold chain breaches]
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Excursion Rate
    expr: MEASURE(`Temperature Excursions`) / NULLIF(MEASURE(`Shipments`), 0)
    synonyms: [percent out of spec, breach rate]
    format: {type: percentage, decimal_places: {type: max, places: 1}}

  # ── Procedure risk ──────────────────────────────────────────
  - name: Procedures at Risk
    expr: |
      COUNT(DISTINCT source.shipment_id) FILTER (
        WHERE source.status <> 'Delivered'
          AND source.eta_date > source.procedure_date)
    comment: "Active shipments whose ETA is after the scheduled procedure date (same rule as the app's Network Map and Genie)."
    synonyms: [surgeries at risk, cases at risk, procedure risk, late for surgery]
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: STAT Procedures at Risk
    expr: |
      COUNT(DISTINCT source.shipment_id) FILTER (
        WHERE source.status <> 'Delivered'
          AND source.priority = 'STAT'
          AND source.eta_date > source.procedure_date)
    comment: "Procedures at Risk with STAT priority (needed for a scheduled procedure). These go to immediate escalation."
    synonyms: [critical at risk, stat risk, escalations needed]
    format: {type: number, decimal_places: {type: exact, places: 0}}

  # ── Distance ────────────────────────────────────────────────
  - name: Avg Route Miles
    expr: AVG(source.route_miles)
    synonyms: [average distance, route length]
    format: {type: number, decimal_places: {type: exact, places: 0}}
$$;
