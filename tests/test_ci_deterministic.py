"""Deterministic CI tests for the RAG chatbot. Run from the project root: pytest -v

These cover the stable parts of the pipeline: PDF ingestion, chunking, TF-IDF indexing, retrieval,
and the no-LLM fallback answer. They make no network or LLM API calls, so they give the same result
on every run and on every machine. The live-LLM tests are in test_rag_system.py.
"""
import logging

import pytest

from app import (
    PDF_DIR,
    answer_with_context,
    answer_with_llm,
    build_knowledge_base,
    clean_text,
    split_text,
)

logging.getLogger("streamlit").setLevel(logging.ERROR)  # silence "no ScriptRunContext" noise outside Streamlit


@pytest.fixture(scope="session")
def kb():
    """Build the TF-IDF index once for the whole test session."""
    return build_knowledge_base(str(PDF_DIR))


# --- Chunking and text cleaning (pure functions) ---

def test_split_text_respects_size_and_overlap():
    words = [str(n) for n in range(25)]
    chunks = list(split_text(" ".join(words), size=10, overlap=2))
    assert all(len(chunk.split()) <= 10 for chunk in chunks)
    assert chunks[0].split()[-2:] == chunks[1].split()[:2]  # 2-word overlap between neighbours
    assert chunks[-1].split()[-1] == "24"  # nothing is dropped at the end


def test_split_text_of_empty_page_gives_no_chunks():
    assert list(split_text("   ")) == []


def test_clean_text_joins_hyphenated_line_breaks():
    assert clean_text("exam-\nple   text\n\nhere") == "example text here"


# --- PDF ingestion and indexing ---

def test_rag_builds_index(kb):
    assert len(kb.chunks) > 0
    assert len(kb.files) == 6


def test_every_chunk_has_a_source_and_page(kb):
    for chunk in kb.chunks:
        assert chunk.text.strip()
        assert chunk.source in kb.files
        assert chunk.page >= 1


# --- Retrieval ---

def test_retrieval_returns_results(kb):
    results = kb.search("AI software developer productivity", limit=3)
    assert len(results) > 0


def test_top_k_is_respected(kb):
    results = kb.search("software development", limit=2)
    assert len(results) <= 2


def test_results_are_ranked_by_score(kb):
    scores = [score for _, score in kb.search("software development", limit=5)]
    assert scores == sorted(scores, reverse=True)
    assert all(score > 0 for score in scores)


def test_retrieval_finds_the_right_document(kb):
    results = kb.search("METR randomized controlled trial open-source developers completion time", limit=5)
    assert results[0][0].source == "MEASUR_1.PDF"


def test_nonsense_query_returns_nothing(kb):
    assert kb.search("zzzqqqxxyy plugh", limit=5) == []


# --- Answering without an LLM ---

def test_fallback_answer_names_the_source(kb):
    results = kb.search("METR randomized controlled trial open-source developers completion time", limit=5)
    answer = answer_with_context("How did AI affect completion time?", results)
    assert "MEASUR_1.PDF" in answer


def test_fallback_answer_with_no_results_says_so():
    assert "could not find" in answer_with_context("anything", []).lower()


def test_llm_is_skipped_without_an_api_key(kb, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    results = kb.search("software development", limit=2)
    assert answer_with_llm("software development", results) is None
