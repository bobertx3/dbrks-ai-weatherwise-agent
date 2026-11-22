"""Build dashboards/weatherwise_insights.lvdash.json from ds_ship.sql / ds_inv.sql.

Run from the repo root: python3 dashboards/build_dashboard.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ship_sql = open(os.path.join(HERE, 'ds_ship.sql')).read().strip()
inv_sql = open(os.path.join(HERE, 'ds_inv.sql')).read().strip()
def lines(sql): return [l + "\n" for l in sql.splitlines()]

TEAL, CORAL, AMBER, BLUE, VIOLET, GREEN, SOFT = "#4FD1C5", "#F2725E", "#E6AB4B", "#6F9CF2", "#9B87F5", "#7FD1A8", "#9DB0C2"
def q(ds, fields, disagg=False, filters=None, name="main_query"):
    d = {"datasetName": ds, "fields": [{"name": n, "expression": e} for n, e in fields], "disaggregated": disagg}
    if filters: d["filters"] = [{"expression": f} for f in filters]
    return [{"name": name, "query": d}]
def frame(t, desc=None):
    f = {"showTitle": True, "title": t}
    if desc: f.update(showDescription=True, description=desc)
    return f
def W(name, queries, spec): return {"name": name, "queries": queries, "spec": spec}
def pos(x, y, w, h): return {"x": x, "y": y, "width": w, "height": h}
def text(name, md): return {"name": name, "multilineTextboxSpec": {"lines": md}}
def kpi(name, title, field, expr, desc):
    # Snapshot totals: no `period` encoding (with one, a counter shows only the latest period's value).
    return W(name, q("ds_ship", [(field, expr)]),
             {"version": 2, "widgetType": "counter",
              "encodings": {"value": {"fieldName": field, "displayName": title}},
              "frame": frame(title, desc)})

layout = []
layout.append({"widget": text("header", [
    "# WeatherWise · Temperature-controlled logistics insights\n",
    "**The story:** 130 temperature-sensitive medical shipments are in motion. **11 are already outside their temperature range** (mostly too warm), "
    "and **weather is the #1 cause of delays**, which keeps more product exposed for longer. Use the Filters page to slice by priority, carrier, product or state.\n"]),
    "position": pos(0, 0, 12, 2)})
kpis = [
    ("kpi-active", "Active shipments", "sum(is_active)", "SUM(`is_active`)", "Not yet delivered"),
    ("kpi-excursions", "Out of range now", "sum(is_excursion)", "SUM(`is_excursion`)", "Sensor reading TOO WARM or TOO COLD for the product"),
    ("kpi-delayed", "Delayed (all causes)", "sum(is_delayed)", "SUM(`is_delayed`)", "Active shipments behind their original ETA"),
    ("kpi-weather-delay", "Delayed by weather", "sum(is_weather_delay)", "SUM(`is_weather_delay`)", "Snow, storms, heavy rain"),
]
for i, (n, t, f, e, d) in enumerate(kpis):
    layout.append({"widget": kpi(n, t, f, e, d), "position": pos(3 * i, 2, 3, 3)})

status_colors = [{"value": "In-Transit", "color": TEAL}, {"value": "Delayed", "color": CORAL}, {"value": "Out-for-Delivery", "color": BLUE},
                 {"value": "Label-Create", "color": SOFT}, {"value": "Delivered", "color": "#4A5F73"}]
layout.append({"widget": W("arrivals", q("ds_ship", [("daily(eta_date)", 'DATE_TRUNC("DAY", `eta_date`)'), ("status", "`status`"), ("count(shipment_id)", "COUNT(`shipment_id`)")]),
    {"version": 3, "widgetType": "bar",
     "encodings": {"x": {"fieldName": "daily(eta_date)", "scale": {"type": "temporal"}, "displayName": "Arrival date"},
                   "y": {"fieldName": "count(shipment_id)", "scale": {"type": "quantitative"}, "displayName": "Shipments"},
                   "color": {"fieldName": "status", "scale": {"type": "categorical", "mappings": status_colors}, "displayName": "Status"}},
     "annotations": [{"type": "vertical-line", "encodings": {"x": {"dataValue": "2026-11-19T00:00:00.000", "dataType": "DATETIME"},
                      "label": {"value": "Today"}, "color": {"value": {"hex": AMBER}}}}],
     "frame": frame("Shipments by arrival date", "Delayed shipments stay in transit longer, so they face more of the weather")}),
    "position": pos(0, 5, 8, 6)})
cause_colors = [{"value": "Weather", "color": CORAL}, {"value": "Dock hold", "color": AMBER}, {"value": "Carrier & network", "color": BLUE},
                {"value": "Equipment", "color": VIOLET}, {"value": "Paperwork", "color": SOFT}]
layout.append({"widget": W("delay-cause", q("ds_ship", [("delay_cause", "`delay_cause`"), ("sum(is_delayed)", "SUM(`is_delayed`)")], filters=["`is_delayed` = 1"]),
    {"version": 3, "widgetType": "bar",
     "encodings": {"x": {"fieldName": "sum(is_delayed)", "scale": {"type": "quantitative"}, "displayName": "Delayed shipments"},
                   "y": {"fieldName": "delay_cause", "scale": {"type": "categorical", "sort": {"by": "value"}}, "displayName": "Cause"},
                   "color": {"fieldName": "delay_cause", "scale": {"type": "categorical", "mappings": cause_colors}, "legend": {"hide": True}},
                   "label": {"show": True}},
     "frame": frame("Why shipments are delayed", "Weather causes more delays than anything else")}),
    "position": pos(8, 5, 4, 6)})
layout.append({"widget": W("excursions", q("ds_ship", [("product", "`product`"), ("temp_status", "`temp_status`"), ("sum(is_excursion)", "SUM(`is_excursion`)")], filters=["`is_excursion` = 1"]),
    {"version": 3, "widgetType": "bar",
     "encodings": {"x": {"fieldName": "sum(is_excursion)", "scale": {"type": "quantitative"}, "displayName": "Shipments out of range"},
                   "y": {"fieldName": "product", "scale": {"type": "categorical", "sort": {"by": "value"}}, "displayName": "Product"},
                   "color": {"fieldName": "temp_status", "scale": {"type": "categorical", "mappings": [{"value": "Too warm", "color": CORAL}, {"value": "Too cold", "color": BLUE}]}, "displayName": "Excursion"}},
     "frame": frame("Out of range by product: too warm vs too cold", "Latest sensor reading vs each product's own range")}),
    "position": pos(0, 11, 6, 6)})
layout.append({"widget": W("carrier-delays", q("ds_ship", [("carrier", "`carrier`"), ("delay_cause", "`delay_cause`"), ("sum(is_delayed)", "SUM(`is_delayed`)")], filters=["`is_delayed` = 1"]),
    {"version": 3, "widgetType": "bar",
     "encodings": {"x": {"fieldName": "carrier", "scale": {"type": "categorical", "sort": {"by": "value"}}, "displayName": "Carrier"},
                   "y": {"fieldName": "sum(is_delayed)", "scale": {"type": "quantitative"}, "displayName": "Delayed shipments"},
                   "color": {"fieldName": "delay_cause", "scale": {"type": "categorical", "mappings": cause_colors}, "displayName": "Cause"}},
     "frame": frame("Delays by carrier and cause", "FedEx Cold has the most delays, averaging ~24h")}),
    "position": pos(6, 11, 6, 6)})
layout.append({"widget": W("dest-map", q("ds_ship", [("lat", "`lat`"), ("lon", "`lon`"), ("sum(is_active)", "SUM(`is_active`)"), ("sum(is_excursion)", "SUM(`is_excursion`)")], filters=["`is_active` = 1"]),
    {"version": 2, "widgetType": "symbol-map",
     "encodings": {"coordinates": {"latitude": {"fieldName": "lat"}, "longitude": {"fieldName": "lon"}},
                   "size": {"fieldName": "sum(is_active)", "scale": {"type": "quantitative"}, "displayName": "Active shipments"},
                   "color": {"fieldName": "sum(is_excursion)", "scale": {"type": "quantitative", "colorRamp": {"mode": "custom-sequential", "colors": {"start": TEAL, "end": CORAL}}}, "displayName": "Excursions"}},
     "mark": {"opacity": 0.8},
     "frame": frame("Where shipments are headed", "Bubble size = active shipments · color = temperature excursions")}),
    "position": pos(0, 17, 7, 7)})
layout.append({"widget": W("inv-heat", q("ds_inv", [("product", "`product`"), ("state", "`state`"), ("sum(on_hand)", "SUM(`on_hand`)")]),
    {"version": 3, "widgetType": "heatmap",
     "encodings": {"x": {"fieldName": "state", "scale": {"type": "categorical"}, "displayName": "State"},
                   "y": {"fieldName": "product", "scale": {"type": "categorical"}, "displayName": "Product"},
                   "color": {"fieldName": "sum(on_hand)", "scale": {"type": "quantitative", "colorRamp": {"mode": "custom-sequential", "colors": {"start": "#16323A", "end": TEAL}}}, "displayName": "Units on hand"},
                   "label": {"show": True}},
     "frame": frame("Backup stock: units on hand by product and state", "Gaps = no backup nearby; NY has only 4 aortic valves")}),
    "position": pos(7, 17, 5, 7)})
cols = [("shipment_id", "Shipment"), ("priority", "Priority"), ("product", "Product"), ("facility", "Destination"), ("status", "Status"),
        ("eta_date", "ETA"), ("sensor_f", "Sensor °F"), ("min_f", "Min °F"), ("max_f", "Max °F"), ("temp_status", "Temperature"), ("delay_reason", "Delay reason")]
table_cols = []
for f, d in cols:
    c = {"fieldName": f, "displayName": d}
    if f == "temp_status":
        c["style"] = {"type": "basic", "rules": [{"condition": {"operand": {"type": "data-value", "value": "In range"}, "operator": "!="}, "backgroundColor": {"hex": "#5A2A24"}}]}
    table_cols.append(c)
layout.append({"widget": W("at-risk-table", q("ds_ship", [(f, f"`{f}`") for f, _ in cols], disagg=True, filters=["`is_excursion` = 1 OR `is_weather_delay` = 1"]),
    {"version": 2, "widgetType": "table", "encodings": {"columns": table_cols},
     "frame": frame("Weather & temperature risk", "Out of range now, or held by weather in transit")}),
    "position": pos(0, 24, 12, 7)})

def flt(name, field, title):
    qn = f"f_{field}"
    return {"widget": {"name": name, "queries": q("ds_ship", [(field, f"`{field}`")], name=qn),
            "spec": {"version": 2, "widgetType": "filter-multi-select",
                     "encodings": {"fields": [{"fieldName": field, "displayName": title, "queryName": qn}]}, "frame": frame(title)}}}
filters = [flt("filter-priority", "priority", "Priority"), flt("filter-carrier", "carrier", "Carrier"),
           flt("filter-product", "product", "Product"), flt("filter-state", "dest_state", "Destination state")]
for i, f in enumerate(filters):
    f["position"] = pos(3 * i, 0, 3, 2)

dash = {
    "datasets": [
        {"name": "ds_ship", "displayName": "Shipments", "queryLines": lines(ship_sql)},
        {"name": "ds_inv", "displayName": "Inventory", "queryLines": lines(inv_sql)},
    ],
    "pages": [
        {"name": "overview", "displayName": "Overview", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": layout},
        {"name": "filters", "displayName": "Filters", "pageType": "PAGE_TYPE_GLOBAL_FILTERS", "layoutVersion": "GRID_V1", "layout": filters},
    ],
    "uiSettings": {
        "theme": {
            "canvasBackgroundColor": {"light": "#F4F7FA", "dark": "#0A1017"},
            "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#0E1A26"},
            "widgetBorderColor": {"light": "#FFFFFF", "dark": "#0E1A26"},
            "fontColor": {"light": "#1B2733", "dark": "#DBE4EC"},
            "selectionColor": {"light": "#2BB3A8", "dark": "#4FD1C5"},
            "visualizationColors": [TEAL, CORAL, AMBER, BLUE, VIOLET, GREEN, SOFT],
            "widgetHeaderAlignment": "LEFT",
            "widgetCornerRadius": 10,
        },
        "genieSpace": {"isEnabled": True, "overrideId": "01f170fcaf40172a87ed6c9398d7f2d5", "enablementMode": "ENABLED"},
    },
}
json.dump(dash, open(os.path.join(HERE, 'weatherwise_insights.lvdash.json'), 'w'), indent=2)
print("widgets:", len(layout), "filters:", len(filters))
