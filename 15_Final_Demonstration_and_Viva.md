# 15 — Final Demonstration and Viva

All numbers presented must come from the system's stored runs. If a figure is not in the database or in a saved CSV, do not say it.

## 1. Demonstration script (≈12–15 minutes; adjust to the allotted time)

| Min | Segment | Presenter | What to show |
|---|---|---|---|
| 0–1 | Problem and idea | M3 | PS9 wording; "valid variation vs violation vs deviation"; why FSM + ML |
| 1–4 | Workflow and automata | M1 | Order & Payment DFA diagram; L(M) regular expression; validate one valid, one invalid (red edge), one incomplete trace on page 1 |
| 4–6 | NFA→DFA, minimisation, reachability | M1 | step table; merged states; reachability report; equivalence of hand DFA and derived DFA |
| 6–9 | Data and ML | M2 | generate dataset (seed visible); anomaly classes; train IF; score histogram; leakage controls in one slide |
| 9–11 | Hybrid detection | M1 (cross-module segment) | page 4: one RULE_VIOLATION, one STATISTICAL_ANOMALY, one valid variation correctly not flagged; explanations |
| 11–13 | Evaluation | M3 | FSM-only vs ML-only vs hybrid tables from DB; per-type recall; honest observations incl. what did not work |
| 13–14 | Packet validation | M3 | one slide + page 5: TCP FSM, scenario-agreement table, limitations |
| 14–15 | Architecture, deployment, wrap-up | M2 (cross-module: pipeline end-to-end) | Compose stack, deployed URL, tests/CI, limitations & future work |

**Backup plan:** local stack ready; recorded video of the full flow; screenshots in slides; pre-generated dataset with known seed; warm up hosted services 10 minutes before.

## 2. What to say about limitations (honestly)

- Labels are injected by our generator; results show behaviour on **controlled** anomalies, not real fraud.
- The DFA is hand-designed for one workflow.
- Random Forest is a supervised reference that may learn generator artefacts.
- Packet module: simplified FSM, tiny sample, FSM validity ≠ benign.
- No claims about real-world intrusion detection.

## 3. Viva question banks

### Member 1 (TOC)
1. Define the DFA formally (Q, Σ, δ, q₀, F). Why a *complete* DFA with a dead state?
2. Write L(M) as a regular expression and justify that it is regular.
3. What is the difference between unreachable and dead states? How do you compute each?
4. Explain subset construction on your payment-block example. Why can the DFA blow up?
5. What does minimisation do? Which states did it merge in your workflow and why (Myhill–Nerode)? Why keep the non-minimal DFA for monitoring?
6. How do you check two DFAs are equivalent? What is the counter-example string good for?
7. Give a constraint on this workflow that is not regular (pumping-lemma argument). Why is "at most k retries" regular?
8. Why does an FSM validate a trace in O(n)?
9. How does the hybrid layer ensure a formal violation is never overridden by ML?

### Member 2 (Workflow ML)
1. Why can't the DFA detect 7 payment retries, and how does ML catch it?
2. Explain how Isolation Forest scores a sample. Why unsupervised?
3. List the features. Which features did you exclude and why (leakage)?
4. How is the threshold chosen and why not on the test set?
5. How are labels generated and verified? What is a valid variation and why must it not be flagged?
6. Why is Random Forest only a "supervised reference"?
7. How did you split the data and why by case? What are held-out anomaly types?
8. What would change if you used a real public log?

### Member 3 (Research & Packet)
1. How does the Markov detector work? Mean vs total log-likelihood — what is the difference?
2. What did the detector comparison show? (answer only from stored results) What were the limitations?
3. Explain the hybrid decision table and the ML policy options.
4. How do you map TCP flags to events? Draw the simplified TCP FSM.
5. Why can a legal SYN→RST sequence still be a port scan? What does that say about FSM validity?
6. What do strict vs tolerant profiles represent? How did you show strict ⊂ tolerant?
7. Why is the packet module independent of the main pipeline?
8. What are the causes of false violations on real captures?

### Cross-module (anyone may be asked about anything)
1. Walk through one trace from CSV row to dashboard explanation.
2. Why is accuracy a poor metric here? Which metrics did you use and why?
3. How do you guarantee the dashboard shows no fabricated numbers?
4. What would you do with more time? (bounded-retry DFA in production, k-tails discovery, LSTM, streaming, richer real logs)
5. Where could your evaluation be misleading? (injected labels, base rate, hand-picked parameters)
6. What did each teammate build, and how did you review it?

## 4. Quick answer outlines (for rehearsal, not to be read out)

- **DFA vs ML:** DFA = exact, explainable, linear time, but only symbol-order rules; ML = statistical regularities, approximate, needs calibration. Hybrid = formal verdict first, ML only on valid traces.
- **Regular language:** accepted by a finite automaton; closed under union/concat/star/complement/intersection; cannot count unboundedly.
- **Why NFA:** convenient to describe optional/retry structure with ε-moves; same language class as DFA; subset construction converts.

## 5. Presentation preparation checklist
- [ ] Each member rehearsed their segment and one cross-module segment.
- [ ] Walkthrough swaps (doc 10 §8) completed.
- [ ] All slides' numbers traceable to stored runs (record eval ids in slide notes).
- [ ] Limitations slide included.
- [ ] Demo checklist (doc 12 §7) passed within the last 24 hours.
- [ ] Contribution log up to date.
