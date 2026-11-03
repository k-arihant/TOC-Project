from src.packet.tcp_fsm import load_tcp_dfa


def test_tcp_fsm_loads_successfully():
    strict_dfa = load_tcp_dfa(profile="strict")
    tolerant_dfa = load_tcp_dfa(profile="tolerant")

    assert strict_dfa.start_state == "T0"
    assert strict_dfa.accepting_states == {"T6", "T7"}
    assert tolerant_dfa.start_state == "T0"
    assert tolerant_dfa.accepting_states == {"T6", "T7"}


def test_tcp_fsm_strict_acceptance():
    strict_dfa = load_tcp_dfa(profile="strict")

    # Clean close
    trace_clean = ["SYN", "SYNACK", "ACK", "DATA", "FIN", "FIN", "ACK"]
    assert strict_dfa.accepts(trace_clean) is True
    curr = strict_dfa.start_state
    for sym in trace_clean:
        curr = strict_dfa.step(curr, sym)
    assert curr == "T6"

    # Reset
    trace_reset = ["SYN", "RST"]
    assert strict_dfa.accepts(trace_reset) is True
    curr_reset = strict_dfa.start_state
    for sym in trace_reset:
        curr_reset = strict_dfa.step(curr_reset, sym)
    assert curr_reset == "T7"

    # Illegal transition: DATA before SYN
    assert strict_dfa.accepts(["DATA"]) is False


def test_tcp_fsm_tolerant_repeated_syn():
    strict_dfa = load_tcp_dfa(profile="strict")
    tolerant_dfa = load_tcp_dfa(profile="tolerant")

    # Word with repeated SYN
    trace_syn_retry = ["SYN", "SYN", "SYNACK", "ACK", "FIN", "FIN", "ACK"]

    # Strict rejects repeated SYN
    assert strict_dfa.accepts(trace_syn_retry) is False

    # Tolerant accepts repeated SYN
    assert tolerant_dfa.accepts(trace_syn_retry) is True
    curr = tolerant_dfa.start_state
    for sym in trace_syn_retry:
        curr = tolerant_dfa.step(curr, sym)
    assert curr == "T6"


def test_tcp_fsm_language_inclusion_proof():
    """
    Formal TOC extension per Doc 07 §4.2:
    Prove L(Strict) ⊂ L(Tolerant).
    1. Every string accepted by Strict is accepted by Tolerant.
    2. Strict is a strict subset (witness string accepted by Tolerant but not Strict).
    """
    strict_dfa = load_tcp_dfa(profile="strict")
    tolerant_dfa = load_tcp_dfa(profile="tolerant")

    # Representative suite of valid Strict strings
    strict_samples = [
        ["SYN", "RST"],
        ["SYN", "SYNACK", "RST"],
        ["SYN", "SYNACK", "ACK", "FIN", "FIN", "ACK"],
        ["SYN", "SYNACK", "ACK", "DATA", "FIN", "FIN", "ACK"],
        ["SYN", "SYNACK", "ACK", "DATA", "DATA", "FIN", "FIN", "ACK"],
        ["SYN", "SYNACK", "ACK", "DATA", "FIN", "RST"],
    ]

    for word in strict_samples:
        assert strict_dfa.accepts(word) is True, f"Strict should accept {word}"
        assert tolerant_dfa.accepts(word) is True, f"Tolerant must accept strict word {word}"

    # Witness 1: Repeated SYN
    w1 = ["SYN", "SYN", "SYNACK", "ACK", "FIN", "FIN", "ACK"]
    assert not strict_dfa.accepts(w1) and tolerant_dfa.accepts(w1)

    # Witness 2: Trailing ACK in T6
    w2 = ["SYN", "SYNACK", "ACK", "FIN", "FIN", "ACK", "ACK"]
    assert not strict_dfa.accepts(w2) and tolerant_dfa.accepts(w2)
