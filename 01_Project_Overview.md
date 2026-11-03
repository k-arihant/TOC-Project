# 01 — Project Overview

**Project title:** Anomaly Detection in Process Workflows Using Automata and Machine Learning
**Course context:** Theory of Computation (TOC) — TA Activity, Problem Statement 9 (PS9)
**Team:** 3 members (see `10_Team_Distribution.md`)
**Document status:** Planning blueprint. Nothing described here has been implemented or measured yet. No results are claimed anywhere in this documentation set.

> Legend used across all documents
> **[M]** Mandatory (stated in PS9 or in our project brief) · **[R]** Recommended (strongly advised, low risk) · **[E]** Optional enhancement (only if ahead of schedule)

---

## 1. Problem statement (professor's PS9, summarised faithfully)

Develop an intelligent workflow-monitoring system that represents normal business or software processes as finite-state machines and applies machine learning to identify unusual execution sequences. Example applications named by the PS: student registration, online payment processing, hospital appointment workflows, order management. The system must **distinguish valid process variations from sequences that violate predefined rules or significantly deviate from observed behaviour.**

PS9 objectives (verbatim intent, re-ordered only for numbering):

1. Select a workflow and define its states, events, and transition rules.
2. Generate or collect event logs containing normal and anomalous sequences.
3. Build a finite-state model to identify invalid transitions.
4. Train ML models to detect statistical or sequential anomalies.
5. Combine rule-based violations with ML anomaly scores.
6. Evaluate detection performance and explain why each sequence was flagged.

PS9 TOC concepts: state-transition systems, DFA, regular languages, reachability.
PS9 ML techniques: Isolation Forest, clustering, Random Forest, sequence models.
PS9 expected outcome: a workflow-monitoring **dashboard** that displays execution paths, highlights unusual transitions, and reports anomaly scores.

## 2. Our selected workflow and why

**Selected workflow: Online Order & Payment Lifecycle.**

| Criterion | Why this workflow wins |
|---|---|
| Matches PS9 examples | Combines two named examples: "online payment processing" and "order management". |
| Natural optional paths | Payment retry, cancellation before/after payment, refund after delivery — exactly the "valid process variations" the PS asks us to distinguish from anomalies. |
| Meaningful formal rules | Strong ordering constraints (cannot ship before payment authorised; nothing after Closed) give crisp, explainable DFA violations. |
| Meaningful statistical anomalies | Excessive payment retries and abnormal inter-event timing are *legal* for the DFA but unusual — this is where ML must add value. |
| Interesting automata theory | The hand-designed DFA is deliberately **not minimal** (states `Created` ≡ `PaymentFailed`, and `CancelledUnpaid` ≡ `Refunded`), so minimisation is a real, demonstrable result, not a toy. |
| Familiar to evaluators | No domain knowledge needed; easy to demo live. |

Alternatives considered and rejected: hospital appointment (more domain explanation needed, fewer natural timing anomalies); student registration (few failure/retry paths); TCP lifecycle as the *main* workflow (would turn the project into a networking project — rejected by our brief).

## 3. Project direction (decided)

"Option 2 — Real packet data as a small validation layer."

- The **main system** is a TOC project: DFA/NFA, NFA→DFA, minimisation, reachability, regular languages, rule-based + ML + hybrid detection, explainability.
- A **separate, independent supplementary module** applies the same automata-validation idea to a *simplified TCP connection lifecycle* on a small set of packet-derived sequences.
- Packet work is **capped at ≈10–15 % of total project effort** (planning estimate ≈10–11 %; see `10_Team_Distribution.md`). It is **not** an intrusion-detection system and makes no attack-detection claims.

## 4. Abstract (draft for the report)

Business and software processes follow rules that can be formalised as finite-state machines, and the set of valid execution traces of such a process forms a regular language. This project models an online order-and-payment workflow as a DFA, validates event traces against it in linear time, and reports the exact failing transition for any rule violation. Because a finite automaton cannot express statistical regularities — such as an unusually high number of payment retries or abnormal timing between events — the system complements it with machine-learning anomaly detectors (Isolation Forest and a first-order Markov sequence model, with an optional supervised Random Forest baseline). A hybrid decision layer keeps formal violations and statistical anomalies separate while producing a single, explainable verdict per trace. We evaluate FSM-only, ML-only, and hybrid detection on controlled, reproducibly generated event logs with documented anomaly injection, and report precision, recall, F1, false-positive rate, confusion matrices, and processing time. A small, independent experiment applies a simplified TCP-connection automaton to packet-derived sequences to show the approach transfers to another state-based system, with its limitations stated. The system is delivered as a REST API, a relational database, and an interactive dashboard.

## 5. Motivation

- Rule checking alone (the DFA) is exact but blind to anything that is *legal yet suspicious*.
- ML alone is flexible but opaque and can flag legal behaviour or miss clear rule violations.
- A hybrid keeps formal correctness as the reference and uses ML only where formal rules cannot speak — the central academic point of the project.

## 6. Objectives

**Academic objectives**
1. [M] Formally define the workflow DFA (5-tuple, δ, language L).
2. [M] Implement DFA, NFA, NFA→DFA (subset construction), DFA minimisation, reachability / dead-state / unreachable-state analysis, DFA equivalence checking.
3. [M] Show L is regular and explain what a DFA cannot express (motivating ML).
4. [M] Compare FSM-only, ML-only, hybrid detection.

**Engineering objectives**
5. [M] Reproducible dataset generation and preprocessing.
6. [M] ML module (Isolation Forest) + Markov baseline; Random Forest only where labels are reliable ([R] with caveats in doc 05).
7. [M] Database, REST API, dashboard, tests, Docker, deployment.
8. [M] Supplementary packet-validation experiment (small, independent).

## 7. Scope

**In scope:** one primary workflow; synthetic controlled event logs with injected anomalies; CSV ingestion of event logs; explainable rule + ML + hybrid detection; dashboard; independent TCP packet experiment on a small capture.

**Out of scope (explicit):**
- Real-time stream processing, Kafka, distributed systems.
- Claiming real-world fraud/attack detection.
- Network intrusion detection, attack classification, or any claim that an FSM-invalid TCP flow is malicious.
- Deep-learning models (LSTM/Transformer) — [E] only.
- Authentication/multi-user management beyond an optional API key.

## 8. Limitations (to be repeated honestly in the final report)

1. Main-workflow anomaly labels are **injected by our own generator**; they are controlled ground truth, **not** real-world fraud labels. Any supervised model may learn generator artefacts.
2. A single hand-designed workflow limits generality; the optional public-log experiment is qualitative only.
3. The simplified TCP FSM does not model retransmission, reordering, simultaneous open/close, or mid-stream captures in full.
4. Results depend on our injection parameters; they must be reported with those parameters and multiple random seeds.

## 9. Document map

See `README.md` for the full list of documents and a suggested reading order.
