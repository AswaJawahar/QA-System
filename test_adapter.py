import logging
import os
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

# app.py never loads .env, so load it here
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

logging.getLogger("streamlit").setLevel(logging.ERROR)  # silence "no ScriptRunContext" noise outside Streamlit

import app  # noqa: E402
from app import answer_with_context, answer_with_llm, build_knowledge_base  # noqa: E402

# app.py indexes APP_DIR, but the PDFs live in "PDF Files/" -- point the tests at the real corpus.
PDF_DIR = Path(__file__).resolve().parent / "PDF Files"
TOP_K = 5
_kb = None

# Gemini free tier allows 5 requests/minute per model, so space calls out (default 13 s).
# The wait is reported separately so response-time tests (R5) measure the system, not the throttle.
MIN_INTERVAL = float(os.getenv("LLM_MIN_INTERVAL", "13"))
_last_call = 0.0
last_wait_seconds = 0.0

# app.answer_with_llm swallows LLM errors via st.warning, which is invisible outside Streamlit.
# Capture them so a silent fallback to raw-passage mode shows up in test evidence.
last_llm_error = None


def _record_warning(message, *args, **kwargs):
    global last_llm_error
    last_llm_error = str(message)
    print(f"[adapter] LLM fallback: {message}", file=sys.stderr)


def _get_kb():
    global _kb
    if _kb is None:
        _kb = build_knowledge_base(str(PDF_DIR))
    return _kb


def _throttle():
    global _last_call, last_wait_seconds
    wait = max(0.0, _last_call + MIN_INTERVAL - time.perf_counter())
    if wait:
        time.sleep(wait)
    last_wait_seconds += wait
    _last_call = time.perf_counter()


def ask_chatbot(question: str) -> str:
    global last_llm_error, last_wait_seconds
    last_wait_seconds = 0.0
    results = _get_kb().search(question, limit=TOP_K)
    response = None
    for attempt in range(2):
        last_llm_error = None
        _throttle()
        with mock.patch.object(app.st, "warning", _record_warning):
            response = answer_with_llm(question, results)
        # Retry once on a per-minute rate limit; a daily-quota 429 or other error is not retried.
        if response or not last_llm_error or "429" not in last_llm_error or "per day" in last_llm_error:
            break
        time.sleep(25)
        last_wait_seconds += 25
    return response or answer_with_context(question, results)


if __name__ == "__main__":
    kb = _get_kb()
    print(f"{len(kb.files)} PDFs, {len(kb.chunks)} chunks: {kb.files}")
    print(ask_chatbot("What does the enterprise AI report say about adoption?"))
