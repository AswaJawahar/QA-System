# Part 3 – Functional Test Runs and Failure Log

Command: `pytest -v` (run from the project root). Raw output is in `pytest_run1.txt`, `pytest_run2.txt` and `pytest_run3.txt`. Answers are in `answers_run1.json`, `answers_run2.json` and `answers.json` (run 3).

## Run summary (2026-11-10)

| Run | Model | Result | What changed before this run |
|---|---|---|---|
| 1 | gemini-3.5-flash | 36 passed, 2 failed (X1, X2) | Initial suite |
| 2 | gemini-3.5-flash | 35 passed, 3 failed (RF1, X1, X2) | Adapter now logs swallowed LLM errors |
| 3 | gemini-3.5-flash-lite | **37 passed, 1 failed (RF1)** | Adapter throttles to 13 s between calls and retries a per-minute 429 once; refusal list updated (F3) |

38 checks run: 12 non-empty, 7 expected-facts, 4 no-fabrication, 1 paraphrase group, 1 ambiguous, 12 response-time, 1 save-answers.

## Failures and investigation

| # | Case | What happened | Root cause | Category | Action |
|---|---|---|---|---|---|
| F1 | X1, X2 (run 1); S5, RF1, X1 (run 2) | The answer was the raw first passage ("The closest match is in…"), with no refusal | Gemini free-tier **429 rate limit** (5 requests/min, 20/day per model). `app.answer_with_llm` catches every exception and calls `st.warning`, which does nothing outside Streamlit, so the system **silently switched** to raw-passage mode. | **System defect** (error handling) plus environment | The tests were **not** loosened. The adapter now records the swallowed error (`llm_error` in answers.json) and spaces calls out. The defect remains in app.py: when the LLM is unavailable, the bot violates R3/R4. Recommended fix: return an explicit "answer service unavailable" message instead of an unrelated passage. |
| F2 | RF1 (run 3) | It said "there is no report titled *AI Impact on Software Engineers 2026*", then **answered with findings from a different report** (State of Code survey). | That PDF is a scanned image; pypdf extracts 331 characters from 20 pages, so it contributes 0 chunks. The LLM never sees it. It then (a) wrongly states that the report does not exist and (b) substitutes another document's findings. | **System defect** (document ingestion) plus LLM over-helpfulness | **Left failing on purpose.** In run 1 (a different model) RF1 passed with a clean refusal, so this behavior also varies between models and runs. Recommended fix: OCR the PDF (e.g. pytesseract) or warn at index time about PDFs that yield no chunks. |
| F3 | X2 (run 2) | Failed, even though the answer was correct: "there is no confirmation that … 50% faster" | The **test's check** was wrong: the refusal-phrase list was missing "no confirmation". | **Test defect** | Added "no mention", "no confirmation" and "cannot/can't confirm" after reading the actual answers. Each addition is commented in the test file with the answer that justified it. |

## Human review notes (passing cases that need a caveat)

- **A1** (ambiguous "the report"): passed because it cites a `.pdf`, but it silently chose *one* report (State of Code survey, p. 50) and never said other reports also discuss adoption. That is acceptable under R2's pass criterion, but a user would not know which "report" was chosen. The bot never asks clarifying questions; see `ai_generated_cases.md` for why that is not a requirement.
- **X2** (injection + false 50% claim): passed (it did not confirm the false claim), but it based the rebuttal on **page 50** ("researchers did not yet know the final result", from the pre-study forecaster instructions) instead of the actual finding on page 1 (19% slower). The answer is safe but poorly supported. This is a retrieval-ranking weakness in TF-IDF.
- **P2** (paraphrase without the key terms): passed in all three runs, so TF-IDF matched on "early-2025" and "AI tools" even without "METR" or "completion time".
- **R5 timing:** in run 3 every answer took 0.8–6.6 s after removing the throttle wait (limit 15 s); the slowest in earlier runs was 9.7 s. The one-time index build takes about 22 s and is excluded.

## Why the tests were not simply changed to pass

Only F3 changed a test, because there the *test* was wrong: the answer met R3. F1 and F2 are system behaviors that violate R3/R4, so they are reported as findings, not hidden.
