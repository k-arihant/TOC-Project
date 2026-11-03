# 09 — Frontend and Dashboard (Streamlit)

**Core rule:** the dashboard is a *pure API client*. It imports no ML or automata code and contains **no hardcoded numbers**. When the API has no data it shows an explicit empty state ("No evaluation runs yet — run one from the Evaluation page") instead of placeholders. This is how we guarantee no dummy metrics.

## 1. Pages, owners, and what each must show

| Page file | Owner | Content | API calls |
|---|---|---|---|
| `app.py` (shell, navigation, shared components, API client, report download helper) | **M2** primary; M1 reviewer; M3 contributor | Home: project summary, health indicator, dataset selector stored in session state | `/health`, `/datasets` |
| `pages/1_Automata_Explorer.py` | **M1** | (a) DFA diagram with accepting states; (b) transition table; (c) **Trace Inspector**: paste/select a trace → path drawn over the DFA, **failing edge in red**, allowed events listed; (d) NFA → DFA step table; (e) minimisation view with merged states; (f) reachability report | #3–#8 |
| `pages/2_Workflow_Data_and_ML.py` | **M2** | Generate/upload dataset; dataset stats; class balance; train detectors; score histograms by class; ROC/PR; feature-deviation view for a selected case | #9–#17 |
| `pages/3_Evaluation.py` | **M3** primary (owns the evaluation harness); M2 contributes the ROC/PR/score-histogram components reused from page 2; M1 reviewer | FSM-only vs ML-only vs hybrid table; confusion matrices; per-anomaly-type recall; FPR on `valid_variation`; latency; run history | #22–#23 |
| `pages/4_Hybrid_Detection.py` | **M1** primary (deliberately rotated: M1 must understand and present the hybrid layer); M3 reviewer for decision/explanation semantics; M2 contributor | Batch run; results table with final label, rule verdict, ML scores; filter by label; case drill-down with **explanation text, execution path, anomaly scores**; aggregate **edge-frequency** view over the DFA; download CSV/JSON | #18–#21, #24 |
| `pages/5_Packet_Validation.py` | **M3** primary; M1 reviewer (automata reuse) | Clearly marked **"Supplementary experiment — not part of the main workflow pipeline"**; upload/select capture; verdict distribution; scenario-agreement table; flow drill-down with TCP FSM path; limitations panel | #25–#26 |

## 2. Execution-path visualisation (PS9 expected outcome)

Mechanism: the API returns DOT text (`/workflows/{id}/automaton` plus `highlight` parameters or the validate response). The dashboard renders with `st.graphviz_chart`.

- Visited states/edges: bold blue.
- Failing transition: red edge, offending state outlined red, event label in red.
- Unvisited: grey.
- For aggregate view: edge penwidth proportional to the count of traces using that edge (computed by the API from `fsm_results.state_path`).

If the Graphviz system binary is unavailable in a deployment, fall back to showing DOT in a code block plus a Plotly Sankey/graph built from the same JSON (Member 1 decides at implementation time; record the choice).

## 3. Wireframes

```
Hybrid Detection page
+--------------------------------------------------------------------+
| Dataset [v]  Split [v]  Models [multi]  ML policy [any v]  [Run]    |
+--------------------------------------------------------------------+
| Counts: NORMAL n | RULE_VIOLATION n | STATISTICAL n | IN_PROGRESS n |  <- from API
+--------------------------------------------------------------------+
| Table: case | final label | FSM verdict | IF score | Markov score   |
|        (filter, sort, click row)                          [Download] |
+--------------------------------------------------------------------+
| Drill-down: Explanation lines | DFA diagram with path/failing edge  |
|             Feature deviations / lowest-probability transitions     |
+--------------------------------------------------------------------+
```

## 4. Visualisations required

1. DFA/NFA diagram with highlighting (Graphviz).
2. Score histograms per class + threshold line (Plotly).
3. ROC and PR curves per detector (Plotly), from stored predictions.
4. Confusion matrices for FSM-only / ML-only / hybrid.
5. Metrics comparison bar chart (precision, recall, F1, FPR).
6. Per-anomaly-type recall bars.
7. Latency box/bar (median, p95).
8. Packet-verdict distribution and flow path.

## 5. Downloadable reports

[M] CSV (one row per case: ids, final label, FSM verdict, failing transition, detector scores, explanation text) and JSON (same plus nested evidence) via `st.download_button` using the `/reports/{dataset_id}` endpoint. [E] HTML/PDF summary.

## 6. Quality and UX requirements

- Every chart/table shows dataset id, seed, config hash and model-run id (provenance footer).
- Loading spinners for train/batch calls; clear error messages from the API error format.
- No hidden state: all selections reproducible from the URL/session (Streamlit session state).
- Accessibility: colour is never the only cue (also use line style/labels).
- Manual demo checklist is in doc 12.
