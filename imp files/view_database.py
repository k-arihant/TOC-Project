"""view_database.py — Live CLI explorer for the TOC PS9 Relational Database (ps9.db).

Run this in terminal anytime (e.g. during viva) to demonstrate direct SQL database queries:
    python view_database.py
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps9.db")
if not os.path.exists(DB_PATH):
    DB_PATH = r"D:\5th sem\TOC\TOC-Project-Git\ps9.db"


def print_banner():
    print("\n" + "=" * 68)
    print("  🗄️ TOC-PROJECT PS9 — RELATIONAL DATABASE EXPLORER")
    print(f"  Physical DB File: {DB_PATH}")
    print("=" * 68)


def get_connection():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def show_overview():
    conn = get_connection()
    cur = conn.cursor()
    print("\n--- DATABASE TABLES & ROW COUNTS ---")
    tables = [
        ("workflows", "Process definitions and versioning"),
        ("workflow_events", "Alphabet Σ (11 discrete event symbols)"),
        ("automata", "DFA, NFA, and Minimized DFA state models"),
        ("automaton_states", "All 31 states across the automata"),
        ("automaton_transitions", "All 291 transitions in the transition functions"),
        ("datasets", "Ground-truth simulation batches with seeds"),
        ("cases", "500 transaction traces (Train, Val, Test splits)"),
        ("event_log", "3,733 timestamped microsecond event logs"),
        ("model_runs", "4 trained ML models (serialized BLOB artifacts)"),
        ("ml_predictions", "424 individual ML scores across test cases"),
        ("fsm_results", "106 deterministic DFA validation runs"),
        ("hybrid_decisions", "106 final 4-row hybrid verdicts"),
        ("explanations", "823 synthesized forensic XAI explanations"),
    ]
    print(f"{'Table Name':<25} | {'Rows':<8} | {'Description'}")
    print("-" * 68)
    for tbl, desc in tables:
        try:
            cnt = cur.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
            print(f"{tbl:<25} | {cnt:<8} | {desc}")
        except Exception:
            pass
    conn.close()


def show_decisions():
    conn = get_connection()
    cur = conn.cursor()
    print("\n--- STORED HYBRID DECISIONS (Sample of 106 Pre-Evaluated Cases) ---")
    rows = cur.execute("""
        SELECT d.decision_id, c.case_id, d.final_label, d.reason_code, d.decided_at
        FROM hybrid_decisions d
        JOIN cases c ON d.case_pk = c.case_pk
        LIMIT 15
    """).fetchall()

    print(f"{'ID':<4} | {'Case ID':<12} | {'Final Verdict':<22} | {'Reason Code':<15} | {'Audit Timestamp'}")
    print("-" * 75)
    for r in rows:
        print(f"{r[0]:<4} | {r[1]:<12} | {r[2]:<22} | {r[3]:<15} | {r[4]}")
    conn.close()


def show_fsm_results():
    conn = get_connection()
    cur = conn.cursor()
    print("\n--- FSM VERDICTS & TRAVERSED STATE PATHS (Sample) ---")
    rows = cur.execute("""
        SELECT f.fsm_result_id, c.case_id, f.verdict, f.state_path, f.fail_state
        FROM fsm_results f
        JOIN cases c ON f.case_pk = c.case_pk
        LIMIT 10
    """).fetchall()

    print(f"{'ID':<4} | {'Case ID':<12} | {'Verdict':<16} | {'State Path (Partial)':<30} | {'Fail State'}")
    print("-" * 75)
    for r in rows:
        path_str = str(r[3])[:28] + ".." if len(str(r[3])) > 28 else str(r[3])
        fail_str = str(r[4]) if r[4] else "None (Valid)"
        print(f"{r[0]:<4} | {r[1]:<12} | {r[2]:<16} | {path_str:<30} | {fail_str}")
    conn.close()


def show_models():
    conn = get_connection()
    cur = conn.cursor()
    print("\n--- TRAINED MACHINE LEARNING MODELS & CALIBRATED THRESHOLDS ---")
    rows = cur.execute("""
        SELECT model_run_id, detector, target_fpr, threshold, created_at
        FROM model_runs
    """).fetchall()

    print(f"{'Run ID':<8} | {'Detector Name':<20} | {'Target FPR':<12} | {'Calibrated Threshold'}")
    print("-" * 65)
    for r in rows:
        print(f"{r[0]:<8} | {r[1]:<20} | {str(r[2]):<12} | {r[3]:.4f}")
    conn.close()


def custom_query():
    conn = get_connection()
    cur = conn.cursor()
    print("\nEnter your SQL query (e.g., SELECT * FROM cases WHERE split='test' LIMIT 5;):")
    query = input("SQL > ").strip()
    if not query:
        return
    try:
        rows = cur.execute(query).fetchall()
        cols = [desc[0] for desc in cur.description] if cur.description else []
        print("\nResults:")
        print(" | ".join(cols))
        print("-" * 60)
        for r in rows[:20]:
            print(" | ".join(str(val) for val in r))
        if len(rows) > 20:
            print(f"... and {len(rows)-20} more rows.")
    except Exception as e:
        print(f"SQL Error: {e}")
    finally:
        conn.close()


def main():
    while True:
        print_banner()
        print("  1. View Database Overview & Row Counts (All 13 Tables)")
        print("  2. View Stored Hybrid Decisions (106 Test Cases)")
        print("  3. View FSM State Traversal Paths & Violations")
        print("  4. View Trained ML Models & Calibrated Thresholds")
        print("  5. Run Custom SQL Query on ps9.db")
        print("  0. Exit")
        print("=" * 68)

        choice = input("Select an option (0-5): ").strip()
        if choice == "1":
            show_overview()
        elif choice == "2":
            show_decisions()
        elif choice == "3":
            show_fsm_results()
        elif choice == "4":
            show_models()
        elif choice == "5":
            custom_query()
        elif choice == "0":
            print("\nExiting database explorer. Good luck with your presentation!\n")
            break
        else:
            print("Invalid option. Please choose 0-5.")
        
        input("\nPress Enter to return to menu...")


if __name__ == "__main__":
    # If run with an argument like --overview, just print overview
    if len(sys.argv) > 1 and sys.argv[1] == "--overview":
        print_banner()
        show_overview()
    else:
        main()
