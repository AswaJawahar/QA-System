# QA System Document Chat

A local retrieval-augmented chatbot for the PDF reports in this folder.

## Run

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

In VS Code, start the persistent background task with **Ctrl+Shift+B** and select **Run QA System Chatbot** if prompted. Keep VS Code open while using the app; stop the task from the Terminal panel when finished. Avoid using **Run Python File** for `app.py`, since the chatbot needs a long-running Streamlit server.

The app extracts PDF text, splits it into overlapping chunks, builds a local TF-IDF index, and retrieves the most relevant passages for each question. Answers show the source filename and page number.

### Optional answer synthesis

Retrieval works without credentials. To have an OpenAI-compatible model synthesize an answer from the retrieved passages, set:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "gpt-4o-mini"
# Optional for compatible providers:
$env:OPENAI_BASE_URL = "https://your-provider.example/v1"
```

Then start Streamlit again.

## Testing (Lab 4)

The Lab 4 tests call the live Gemini API, so they are opt-in:

```powershell
py -m pip install -r requirements.txt
$env:RUN_LIVE_LLM_TESTS = "1"
py -m pytest -v          # about 3 minutes: calls are spaced 13 s apart for the Gemini free tier
```

`.env` (gitignored) sets `OPENAI_API_KEY`, `OPENAI_BASE_URL` (Gemini's OpenAI-compatible endpoint) and `OPENAI_MODEL`. The free tier allows about 20 requests per model per day, and one full run uses 12.

| Lab part | File |
|---|---|
| Part 1 – requirements and test oracle | `REQUIREMENTS.md` |
| Part 2 – AI candidates, review, final cases | `ai_generated_cases.md`, `test_results/ai_raw_output.md`, `test_cases.json` |
| Part 3 – automated tests and results | `tests/test_rag_system.py`, `test_results/pytest_run*.txt`, `test_results/answers*.json`, `test_results/failure_log.md` |

`test_adapter.py` connects the tests to `app.py`: it points at `PDF Files/`, records LLM errors that would otherwise be swallowed, and spaces out API calls.

## Continuous integration (DevOps lab)

```powershell
py -m pytest -v          # about 30 seconds: deterministic tests only, no API key needed
```

`.github/workflows/ci.yml` runs the same command on every push and pull request to `main`. It runs only `tests/test_ci_deterministic.py`, which covers PDF ingestion, chunking, indexing, retrieval and the no-LLM fallback. The live-LLM tests in `tests/test_rag_system.py` are skipped unless `RUN_LIVE_LLM_TESTS=1` is set, so CI needs no secrets and gives the same result on every run.
