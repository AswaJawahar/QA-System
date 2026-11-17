"""Live-LLM functional tests for the RAG Q&A chatbot.

Run from the project root with RUN_LIVE_LLM_TESTS=1 set, then: pytest -v

Requirements R0-R5 are defined in REQUIREMENTS.md; test cases live in test_cases.json.
"""
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import test_adapter  # noqa: E402
from test_adapter import _get_kb, ask_chatbot  # noqa: E402

# Every test in this file calls the live LLM, so the whole module is opt-in (see conftest.py).
pytestmark = pytest.mark.live_llm

CASES = json.loads((ROOT / "test_cases.json").read_text(encoding="utf-8"))

# Phrases that count as a conservative "I can't answer from the documents" reply.
REFUSAL_PHRASES = [
    "not in the", "not contain", "doesn't contain", "does not contain",
    "don't know", "do not know", "cannot find", "can't find", "no information",
    "not mentioned", "not provided", "not available", "unable to", "not covered",
    "context does not", "does not provide", "does not answer", "could not find",
    # Added after runs 1-2: correct conservative answers the original list missed
    # (X1 manual re-run: "there is no mention of..."; X2 run 2: "there is no confirmation that...").
    "no mention", "no confirmation", "cannot confirm", "can't confirm",
]

MAX_SECONDS = 15  # R5: response-time limit for a classroom-scale workload (warm index)

_cache = {}
_timings = {}
_llm_errors = {}


def answer(question):
    """Ask each question once per run (saves API calls; RAG output is stochastic)."""
    if question not in _cache:
        start = time.perf_counter()
        _cache[question] = ask_chatbot(question)
        _timings[question] = time.perf_counter() - start - test_adapter.last_wait_seconds
        _llm_errors[question] = test_adapter.last_llm_error
    return _cache[question]


@pytest.fixture(scope="session", autouse=True)
def warm_index():
    """Build the TF-IDF index once up front so R5 timings measure answering, not indexing."""
    _get_kb()


def cases(*categories):
    return [c for c in CASES if c["category"] in categories]


def is_refusal(text):
    t = text.lower()
    return any(p in t for p in REFUSAL_PHRASES)


def case_id(c):
    return c["id"]


# 1. Non-empty response for every question (R0)
@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_returns_non_empty_response(case):
    response = answer(case["question"])
    assert isinstance(response, str) and response.strip(), "Empty or non-string response"


# 2. Supported + paraphrased questions contain expected facts/keywords (R1; oracle = source PDF)
@pytest.mark.parametrize("case", cases("supported", "paraphrase"), ids=case_id)
def test_supported_answer_contains_expected_facts(case):
    response = answer(case["question"]).lower()
    hits = [k for k in case["expected_keywords"] if k.lower() in response]
    needed = case.get("min_keyword_hits", 1)
    assert len(hits) >= needed, (
        f"Found {hits} of {case['expected_keywords']} (needed {needed}). "
        f"Source: {case['source']}\nAnswer: {response[:400]}"
    )


# 3. Out-of-scope / unreadable-source / adversarial questions do not invent an answer (R3, R4)
@pytest.mark.parametrize("case", cases("out_of_scope", "retrieval_failure", "adversarial"), ids=case_id)
def test_does_not_fabricate(case):
    response = answer(case["question"])
    lowered = response.lower()
    # A refusal OR an explicit correction with the true fact from the source both count as conservative.
    rebutted = any(k.lower() in lowered for k in case.get("rebuttal_keywords", []))
    assert is_refusal(response) or rebutted, (
        f"Expected a conservative refusal/rebuttal.\nLLM error: {_llm_errors[case['question']]}\nAnswer: {response[:400]}"
    )
    for bad in case.get("forbidden_keywords", []):
        assert bad.lower() not in lowered, f"Contains forbidden content '{bad}'"


# 4. Paraphrased questions give substantively consistent answers (R2)
GROUPS = sorted({c["paraphrase_group"] for c in CASES if c.get("paraphrase_group")})


@pytest.mark.parametrize("group", GROUPS)
def test_paraphrases_are_consistent(group):
    members = [c for c in CASES if c.get("paraphrase_group") == group]
    keywords = {k.lower() for c in members for k in c["expected_keywords"]}
    for c in members:
        response = answer(c["question"]).lower()
        assert any(k in response for k in keywords), (
            f"{c['id']} answer does not share the group's key facts {keywords}"
        )


# 5. Ambiguous questions are either clarified or explicitly grounded in a named document (R2)
@pytest.mark.parametrize("case", cases("ambiguous"), ids=case_id)
def test_ambiguous_answer_is_grounded(case):
    response = answer(case["question"]).lower()
    asks = any(p in response for p in ["which report", "which document", "please specify", "could you clarify"])
    cites = ".pdf" in response
    assert asks or cites, f"Neither asked for clarification nor named a source.\nAnswer: {response[:400]}"


# 6. Response time (R5)
@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_response_time(case):
    answer(case["question"])
    elapsed = _timings[case["question"]]
    assert elapsed <= MAX_SECONDS, f"{elapsed:.1f}s > {MAX_SECONDS}s limit"


# 7. Save every answer for human review (ambiguous cases + UAT evidence)
def test_zz_save_answers_for_review():
    out_dir = ROOT / "test_results"
    out_dir.mkdir(exist_ok=True)
    records = [
        {"id": c["id"], "category": c["category"], "requirement": c.get("requirement"),
         "question": c["question"], "answer": answer(c["question"]),
         "seconds": round(_timings[c["question"]], 2),
         "llm_error": _llm_errors[c["question"]]}
        for c in CASES
    ]
    (out_dir / "answers.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
