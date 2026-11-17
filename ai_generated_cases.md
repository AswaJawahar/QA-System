# Part 2 – AI-Generated Candidate Test Cases and Critical Review

## 1. Prompt and raw output

I sent the handout's prompt word for word to Gemini (`gemini-3.5-flash`, 2026-11-10):

> "I built a RAG-based Q&A chatbot that answers questions from a fixed set of documents. Generate candidate software test cases covering normal questions, ambiguous questions, unsupported questions, boundary cases, retrieval failures, and possible hallucinations. For each case, provide the input question, expected behavior, and why the case matters."

The unedited response is saved in [`test_results/ai_raw_output.md`](test_results/ai_raw_output.md). It proposed 13 generic cases in 6 categories (1.1 to 6.2). None of them referred to my documents. The examples were made up, such as "warranty for Product X" and "expense report approval".

## 2. Review of each AI suggestion

| AI case | Suggested expectation | Traceable to my requirements? | Decision |
|---|---|---|---|
| 1.1 Direct fact retrieval | Exact answer + citation | **Yes, R1.** Citation format comes from app.py's system prompt. | Kept as the pattern for S1–S5. The facts came from my PDFs, not from the AI. |
| 1.2 Multi-chunk synthesis | Combine two sections | Partly R1 | Adapted as S4 (two figures that must both appear). Within one chunk, because 850-word chunks usually cover a whole page. |
| 2.1 Vague terminology | Ask for clarification **or** summarize each option | **Partly invented.** No requirement says the bot must ask questions back, and app.py's prompt never tells it to. | Adapted as A1 with a looser pass condition: ask for clarification **or** name the source document. |
| 2.2 Pronoun with no context ("What is its price?") | Ask which product | **Invented.** It assumes conversation memory; ask_chatbot() takes one question at a time. | Rejected. |
| 3.1 Out-of-domain (capital of France) | Polite decline | **Yes, R4** | Kept in spirit as O1. I used a FedEx stock question instead, because it fools TF-IDF (score 0.262), which makes it a harder test. |
| 3.2 Topic-related but missing fact | "No mention" rather than "No" | **Yes, R3/R4.** A good distinction. | Covered by X1's pass rule (a refusal, not a counter-claim). |
| 4.1 Prompt injection | Ignore it and fall back | Partly R3. Protecting the system prompt is not one of my requirements. | Adapted as X2: an injection combined with a false fact, judged only on whether it invents something. |
| 4.2 1,000-word noisy input | Find the hidden question | Not in R1–R5 | Postponed to the stress test part. |
| 4.3 Heavy typos | Understand intent | **Invented for this system.** It assumes embedding search; TF-IDF does exact token matching, so typos are *expected* to fail. | Rejected as a pass/fail requirement (noted as a known limitation). |
| 5.1 Synonym mismatch | Semantic search finds it | **Invented.** Again assumes embeddings. | Adapted as P2 (paraphrase with no shared key terms), used to *probe* TF-IDF rather than to assume it works. P2 passed. |
| 5.2 Information split across chunks | Retrieve both chunks | Relevant to chunking design | Not used; the 120-word overlap plus top-5 retrieval makes this hard to set up on purpose. |
| 6.1 False premise | Correct the premise | **Yes, R3** | Kept as X1. |
| 6.2 Speculation request | Refuse to predict | Yes, R3 | Not used (case limit); a good extra case. |
| "Use Ragas/TruLens/DeepEval" | — | Not required | Not used; documented as possible future work. |

Two cases came from my own analysis rather than from the AI: **RF1** (a question about the scanned PDF that has no extractable text) and the specific FedEx wording for **O1**.

## 3. Critical review question

**Which AI-generated expectations actually came from my system requirements, and which did the AI silently invent?**

- **Traceable:** answering supported facts with a citation (R1); declining off-topic questions (R4); saying "not mentioned" rather than making a negative claim, and correcting false premises (R3). These match R1–R4 and app.py's system prompt.
- **Silently invented:**
  1. *The bot asks clarifying questions* (2.1, 2.2). This is a reasonable product idea, but no requirement asks for it, and the system was never designed to do it. A test with this as a hard rule would fail for reasons unrelated to correctness.
  2. *Semantic or embedding retrieval* (4.3, 5.1). The AI assumed a vector database. This system uses TF-IDF, so "robust to typos and synonyms" is a feature the AI made up and then expected.
  3. *Multi-turn memory* (2.2). ask_chatbot() is stateless.
  4. *Keeping the system prompt secret* (4.1). This is a security requirement nobody stated.
  5. *Every expected answer* (warranty periods, refund policies, $50 fees). The AI does not know my documents, so all of its "expected behavior" values were placeholders. **No expected answer in test_cases.json came from the AI.** Every expected keyword was copied from the PDF page listed in `source`.
- **Lesson:** the AI was useful for *coverage* (it named categories I had missed, such as false premises and prompt injection) but not as an *oracle*. Its expectations reflect a generic RAG design, not this system.

## 4. Classmate review

*To fill in after discussion. Record the classmate's name, what they suggested, and what changed in test_cases.json.*

| Suggestion | Accepted? | Change made |
|---|---|---|
| | | |
