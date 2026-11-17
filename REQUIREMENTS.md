# Part 1 – What "Correct" Means for the QA System

**System under test:** `app.py` RAG chatbot. It extracts PDF text with pypdf, splits it into 850-word chunks with a 120-word overlap, retrieves the top 5 chunks with TF-IDF and cosine similarity, and has Gemini write the answer (via Gemini's OpenAI-compatible endpoint, temperature 0; `gemini-3.5-flash-lite` for the final test run, set in `.env`). If the LLM is unavailable, the system returns the best-matching passage instead.

**Corpus:** 6 PDFs in `PDF Files/` (169 chunks).

**Test entry point:** `ask_chatbot(question)` in `test_adapter.py`.

## Requirements

| ID | Requirement | How it is tested | Pass criterion |
|----|-------------|------------------|----------------|
| R1 | Answers questions that the source documents support. | `test_supported_answer_contains_expected_facts` | The answer contains at least `min_keyword_hits` of the expected keywords, which were copied from the source page **before** the test ran. |
| R2 | The answer is relevant to the question. | `test_paraphrases_are_consistent`, `test_ambiguous_answer_is_grounded`, plus human review of `test_results/answers.json` | Paraphrases of one question share the same key facts. Ambiguous questions are answered from a named document or get a request for clarification. |
| R3 | Does not invent unsupported facts. | `test_does_not_fabricate` (adversarial cases) | False premises and prompt injections are rejected; forbidden content does not appear. |
| R4 | Answers unsupported questions cautiously rather than fabricating. | `test_does_not_fabricate` (out-of-scope and retrieval-failure cases) | The answer contains a refusal phrase such as "does not contain" or "not mentioned". |
| R5 | Responds in a reasonable time for a classroom workload. | `test_response_time` | Each answer takes ≤ **15 s**, measured against a warm index; index build time is excluded. |
| R0 | Always returns something. | `test_returns_non_empty_response` | Non-empty string. |

## Test oracle

- **The primary oracle is the source PDF page.** For each factual case in `test_cases.json`, the `source` field gives the file and page, and `expected_keywords` are exact strings (mostly figures such as `19%` or `96%`) taken from that page. I read the PDFs first, wrote down the expected facts, and only then ran the chatbot.
- Neither the LLM under test nor the LLM that suggested test cases defined any expected answer. The AI suggestions affected only *which kinds* of cases to include (see `ai_generated_cases.md`).
- Checks use keywords and concepts, never exact strings, because LLM wording varies.
- The ambiguous case (A1) also gets a **human review** using the saved answers.

## Known constraints found during analysis

1. **`AI Impact on Software Engineers 2026.pdf` is a scanned image.** pypdf extracts only 331 characters from 20 pages, so it adds 0 chunks to the index. Questions about it cannot be answered correctly. The correct behavior is to say so (R4), which test case RF1 checks.
2. **Without an LLM, the fallback never refuses.** Retrieval scores cannot detect unanswerable questions. The FedEx stock-price question scores 0.262, higher than a real developer-survey question (0.128), because "2026" matches a cover page. R3 and R4 therefore depend entirely on the LLM.
3. **The fallback makes keyword tests too easy.** The fallback returns the raw source passage, so keyword checks would pass on retrieval alone. All test results here are with the LLM on.
4. **`app.py` indexed the project root** (`APP_DIR`), but the PDFs are in `PDF Files/`, so the Streamlit app showed "No searchable text was extracted". The tests were never affected because the adapter passes the correct folder. After testing, `app.py` was fixed to use `PDF_DIR` and to load `.env`. No test logic depends on that change.
