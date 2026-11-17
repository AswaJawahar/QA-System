from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import streamlit as st
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


APP_DIR = Path(__file__).resolve().parent
PDF_DIR = APP_DIR / "PDF Files"

try:  # load OPENAI_* settings (Gemini key, endpoint, model) from .env
    from dotenv import load_dotenv

    load_dotenv(APP_DIR / ".env")
except ImportError:
    pass
DEFAULT_CHUNK_SIZE = 850
DEFAULT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    page: int
    chunk_number: int


@dataclass
class KnowledgeBase:
    chunks: list[Chunk]
    vectorizer: TfidfVectorizer
    matrix: object
    files: list[str]

    def search(self, query: str, limit: int = 5) -> list[tuple[Chunk, float]]:
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix).ravel()
        ranked = np.argsort(scores)[::-1]
        return [(self.chunks[index], float(scores[index])) for index in ranked[:limit] if scores[index] > 0]


def clean_text(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> Iterable[str]:
    words = text.split()
    if not words:
        return
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size]).strip()
        if chunk:
            yield chunk
        if start + size >= len(words):
            break


def read_documents(folder: Path) -> tuple[list[Chunk], list[str]]:
    chunks: list[Chunk] = []
    files: list[str] = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() != ".pdf":
            continue
        files.append(path.name)
        reader = PdfReader(str(path))
        for page_number, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            for chunk_number, chunk_text in enumerate(split_text(text), start=1):
                chunks.append(Chunk(chunk_text, path.name, page_number, chunk_number))
    return chunks, files


@st.cache_resource(show_spinner=False)
def build_knowledge_base(folder: str) -> KnowledgeBase:
    chunks, files = read_documents(Path(folder))
    if not chunks:
        raise ValueError("No searchable text was extracted from the PDF files.")
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
    return KnowledgeBase(chunks, vectorizer, matrix, files)


def answer_with_context(query: str, results: list[tuple[Chunk, float]]) -> str:
    if not results:
        return "I could not find a relevant passage in the indexed documents. Try using more specific terms or asking about a named report."
    excerpts = []
    for chunk, _ in results[:3]:
        excerpts.append(f"[{chunk.source}, page {chunk.page}] {chunk.text}")
    best = results[0][0]
    return (
        f"The closest match is in **{best.source}**, page {best.page}.\n\n"
        f"{best.text}\n\n"
        "The passages below are the other closely related excerpts from the QA System."
    )


def answer_with_llm(query: str, results: list[tuple[Chunk, float]]) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not results:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"))
        context = "\n\n".join(
            f"Source: {chunk.source}, page {chunk.page}\n{chunk.text}" for chunk, _ in results
        )
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Answer only from the supplied context. Cite sources as [filename, page N]. If the context does not answer the question, say so.",
                },
                {"role": "user", "content": f"Question: {query}\n\nContext:\n{context}"},
            ],
        )
        return response.choices[0].message.content
    except Exception as exc:
        st.warning(f"LLM answer unavailable; showing the retrieved passages instead. ({exc})")
        return None


def render_source(chunk: Chunk, score: float) -> None:
    with st.expander(f"{chunk.source}  |  page {chunk.page}  |  relevance {score:.2f}"):
        st.write(chunk.text)


def main() -> None:
    st.set_page_config(page_title="QA System | Document Chat", page_icon="Q", layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');
        :root { --ink: #f3efe7; --muted: #b7b2a8; --paper: #171b1e; --accent: #f07158; --line: #3b4448; }
        html, body, [class*="stApp"] { background: var(--paper); color: var(--ink); font-family: 'DM Sans', sans-serif; }
        .block-container { max-width: 1180px; padding-top: 3rem; }
        .eyebrow { color: var(--accent); font-family: 'Space Mono', monospace; font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; }
        h1 { font-size: clamp(2.4rem, 6vw, 5.4rem); line-height: .95; letter-spacing: 0; max-width: 760px; margin: .5rem 0 1rem; }
        .lede { color: var(--muted); font-size: 1.08rem; max-width: 650px; margin-bottom: 2rem; }
        [data-testid="stSidebar"] { background: #232a2e; border-right: 1px solid var(--line); }
        [data-testid="stChatMessage"] { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.06); }
        .source-label { color: var(--muted); font-family: 'Space Mono', monospace; font-size: .76rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="eyebrow">QA SYSTEM / LOCAL RAG</div>', unsafe_allow_html=True)
    st.title("Ask the reports what they know.")
    st.markdown('<div class="lede">Search six research PDFs by meaning, then ground every response in the passages that were actually retrieved.</div>', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### Index")
        st.caption("Documents are read from this folder on startup.")
        top_k = st.slider("Retrieved passages", min_value=2, max_value=8, value=5)
        use_llm = st.toggle("Synthesize with LLM", value=bool(os.getenv("OPENAI_API_KEY")))
        if st.button("Rebuild index", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()

    try:
        knowledge_base = build_knowledge_base(str(PDF_DIR))
    except Exception as exc:
        st.error(f"Could not build the document index: {exc}")
        st.stop()

    with st.sidebar:
        st.markdown(f"**{len(knowledge_base.files)}** PDFs · **{len(knowledge_base.chunks)}** chunks")
        with st.expander("Indexed files"):
            for filename in knowledge_base.files:
                st.write(filename)
        if use_llm and not os.getenv("OPENAI_API_KEY"):
            st.info("Set OPENAI_API_KEY to enable synthesized answers. Retrieval remains local.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.markdown('<div class="source-label">RETRIEVED SOURCES</div>', unsafe_allow_html=True)
                for chunk, score in message["sources"]:
                    render_source(chunk, score)

    query = st.chat_input("Ask about AI jobs, enterprise adoption, developer surveys...")
    if query:
        results = knowledge_base.search(query, limit=top_k)
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
        response = answer_with_llm(query, results) if use_llm else None
        response = response or answer_with_context(query, results)
        st.session_state.messages.append({"role": "assistant", "content": response, "sources": results})
        with st.chat_message("assistant"):
            st.markdown(response)
            if results:
                st.markdown('<div class="source-label">RETRIEVED SOURCES</div>', unsafe_allow_html=True)
                for chunk, score in results:
                    render_source(chunk, score)


if __name__ == "__main__":
    main()
