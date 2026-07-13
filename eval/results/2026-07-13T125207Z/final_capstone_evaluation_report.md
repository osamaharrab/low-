# Lawz AI JO — Final Capstone Evaluation Report

## 1. Executive Summary

This evaluation assessed Lawz AI JO across three independent system-health dimensions: **Fast**, **Reliable**, and **Correct**.

The full RAG system was safer and achieved higher overall correctness than the BM25 top-1 baseline. It increased overall correctness from **32.00%** to **52.00%**, primarily because it correctly abstained on unsupported or out-of-scope questions.

However, legal-answer correctness remained **40.00%**, equal to the baseline. The most important remaining weaknesses were false abstentions on answerable questions, excessive or irrelevant citations, retrieval/source mismatches, and incomplete answers.

The RAG system achieved **99.33%** request success, with an average latency of **6.10 seconds** and p95 latency of **8.79 seconds**.

## 2. Evaluation Design

- Held-out dataset: **50 questions**.
- Answerable legal questions: **40**.
- Expected-abstention questions: **10**.
- BM25 baseline: **50 outputs**.
- Full RAG system: **150 outputs** across seeds `42`, `1337`, and `2024`.
- Human-review rows: **151**.
- Weighted reviewed outputs: **200**.
- Grouped human-review rows were weighted using the values in the `occurrences` column.
- Human-review metrics and automated metrics were kept separate.

## 3. Fast — Latency

| System | Requests | Average latency | Median latency | p95 latency | Maximum latency |
|---|---:|---:|---:|---:|---:|
| BM25 top-1 baseline | 50 | 2.42 ms | 2.35 ms | 3.06 ms | 3.97 ms |
| Full RAG system | 150 | 6097.93 ms | 6107.35 ms | 8788.23 ms | 30130.59 ms |

The local BM25 baseline is expected to be much faster because it does not call the complete API, retrieval, generation, and validation pipeline. The RAG p95 of approximately **8.79 seconds** is usable for an interactive prototype, but the maximum latency of **30.13 seconds** shows that timeout and tail-latency handling still need work.

## 4. Reliable — Request Success and Errors

| System | Success rate | Error rate | 5xx rate | Timeout rate |
|---|---:|---:|---:|---:|
| BM25 top-1 baseline | 100.00% | 0.00% | N/A | 0.00% |
| Full RAG system | 99.33% | 0.67% | 0.67% | 0.67% |

The RAG system completed **149 of 150 requests successfully**. One request in seed `1337` produced a timeout/5xx failure. The other two RAG runs completed without request errors.

## 5. Correct — Human Review

| Metric | BM25 baseline | Full RAG | Difference |
|---|---:|---:|---:|
| Legal correctness on answerable questions | 40.00% | 40.00% | +0.00 pp |
| Evidence supported | 100.00% | 65.00% | -35.00 pp |
| Citation relevance | 50.00% | 12.50% | -37.50 pp |
| Abstention accuracy | 0.00% | 100.00% | +100.00 pp |
| Material hallucination rate | 0.00% | 0.00% | +0.00 pp |
| Overall correctness | 32.00% | 52.00% | +20.00 pp |

Overall correctness combines legally correct answers on answerable questions with correct abstentions on expected-abstention questions.

The baseline's high evidence-support score does not mean its answers were relevant. The baseline copied the retrieved text, so its output was mechanically supported by that text even when the retrieved source did not answer the question.

The RAG system's principal advantage was abstention safety. It correctly declined all expected-abstention cases, while the baseline answered every such question.

## 6. Automated Retrieval and Output Checks

| System | Retrieval hit | Reference hit | Citation validity | False abstention | Correct abstention |
|---|---:|---:|---:|---:|---:|
| BM25 top-1 baseline | 45.00% | 45.00% | 100.00% | 0.00% | 0.00% |
| Full RAG system | 70.00% | 72.50% | 100.00% | 34.17% | 100.00% |

Automated citation validity checks whether returned citations exist in the retrieved candidates; it does not measure whether every citation is semantically relevant to the final answer. This explains the difference between 100% automated citation validity and 12.5% human-reviewed citation relevance.

Automated retrieval and citation checks provide useful regression signals, but they do not replace human legal review.

## 7. Refined Error Analysis

### BM25 baseline

| Failure category | Weighted failures |
|---|---:|
| Retrieval or source mismatch | 20 |
| Failed to abstain | 10 |
| Incomplete or incorrect answer | 4 |

### Full RAG system

| Failure category | Weighted failures |
|---|---:|
| False abstention | 41 |
| Citation selection issue | 40 |
| Retrieval or source mismatch | 23 |
| Incomplete or incorrect answer | 7 |
| Empty or failed generation | 1 |

The broad earlier category `unsupported_or_failed_generation` was refined after inspecting the actual answers. Of its 42 weighted cases:

- **41 were false abstentions** on answerable legal questions.
- **1 was an empty/failed generation**.
- **0 were unsupported generated answers**.

This means the largest weakness was the abstention/evidence-sufficiency gate rather than free-form hallucinated generation.

Error-analysis failure counts use a stricter definition than overall correctness. An output may be legally correct but still be classified as failed because of irrelevant citations or insufficient evidence support.

## 8. Representative Failure Cases

### 8.1 lawz-003 — False abstention

**Question:** عقدي محدد المدة وخلصت مدته بس ضليت أشتغل بنفس المكان، شو بصير بالعقد؟

**Gold answer:** العقد محدد المدة ينتهي من تلقاء نفسه بانتهاء مدته، لكن إذا استمر الطرفان في تنفيذه بعد انقضاء المدة اعتبر ذلك تجديدًا له لمدة غير محدودة من بداية الاستخدام.

**System answer:** لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.

**Reviewer finding:** Incorrect abstention on an answerable legal question.

### 8.2 lawz-030 — Citation selection issue

**Question:** ما مدة الإجازة المرضية المدفوعة، ومتى يمكن تجديدها؟

**Gold answer:** لكل عامل الحق في إجازة مرضية مدتها أربعة عشر يومًا خلال السنة الواحدة بأجر كامل بناء على تقرير من الطبيب المعتمد. ويجوز تجديدها لمدة أربعة عشر يومًا أخرى بأجر كامل إذا كان العامل نزيل أحد المستشفيات، بناء على تقرير طبي معتمد وفق ما ورد في المادة.

**System answer:** الإجابة المختصرة: مدة الإجازة المرضية المدفوعة أربعة عشر يوما خلال السنة الواحدة بأجر كامل، ويجوز تجديدها لمدة أربعة عشر يوما أخرى بأجر كامل إذا كان العامل نزيل أحد المستشفيات. التفسير: تنص النصوص المسترجعة على أن كل عامل يستحق إجازة مرضية مدتها أربعة عشر يوما بأجر كامل بناء على تقرير الطبيب المعتمد، ويجوز تجديدها لأربعة عشر يوما إضافية بأجر كامل في حال الإقامة في المستشفى وفق تقرير طبي معتمد، مع التمييز بين المؤس...

**Reviewer finding:** Answer is correct and supported by Article 65, but additional returned citations concern unrelated leave provisions.

### 8.3 lawz-005 — Retrieval or source mismatch

**Question:** ما أشكال العمل المرن التي يمكن الاتفاق عليها؟

**Gold answer:** يجوز لصاحب العمل والعامل الاتفاق على شكل أو أكثر من العمل المرن، مثل العمل عن بعد، والعمل لبعض الوقت، والعمل ضمن ساعات مرنة، وأسبوع العمل المكثف، والسنة المرنة، وأي شكل يضيفه مجلس الوزراء بناء على تنسيب الوزير.

**System answer:** الإجابة المختصرة: أشكال العمل المرن التي يمكن الاتفاق عليها كتابياً هي: العمل بعض الوقت، أسبوع العمل المكثف، السنة المرنة، والعمل عن بعد. التفسير: يجوز الاتفاق كتابياً بين صاحب العمل والعامل على عقد عمل مرن وفق الأشكال التالية: العمل بعض الوقت بتخفيض ساعات العمل، أسبوع العمل المكثف بتوزيع ساعات الأسبوع على أيام أقل، السنة المرنة بتوزيع أيام العمل السنوي على أشهر محددة، والعمل عن بعد دون تواجد العامل في مكان العمل،...

**Reviewer finding:** Answer omits flexible-hours work and the possibility of additional forms being approved by the Council of Ministers. One returned citation concerns child labour and is unrelated.

### 8.4 lawz-011 — Incomplete or incorrect answer

**Question:** ما الحالات العامة لانتهاء عقد العمل حسب المادة 21؟

**Gold answer:** ينتهي عقد العمل إذا اتفق الطرفان على إنهائه، أو انتهت مدة العقد أو العمل نفسه، أو توفي العامل أو أقعده مرض أو عجز مثبت بتقرير طبي، أو استوفى العامل شروط تقاعد الشيخوخة في قانون الضمان الاجتماعي ما لم يتفق الطرفان على غير ذلك.

**System answer:** الإجابة المختصرة: ينتهي عقد العمل في الحالات التالية: اتفاق الطرفين، انتهاء مدة العقد أو العمل، وفاة العامل أو عجزه بتقرير طبي، أو استيفاء شروط تقاعد الشيخوخة. التفسير: تعتمد الإجابة على النص الصريح للمادة 21 التي تحدد الحالات الأربع العامة لانتهاء عقد العمل، وتؤكدها الوثيقة التوضيحية في الصفحة 33. المراجع: - [1] انتهاء عقد العمل - قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته، المادة 21 - [3] إنهاء عقد العمل وحال...

**Reviewer finding:** Answer omits illness as a medically established termination condition and omits the qualification that the retirement result may differ if the parties agree otherwise.

### 8.5 lawz-006 — Empty or failed generation

**Question:** هل يستطيع صاحب العمل يحول عقدي لعمل مرن من غير موافقتي أو ينتقص من حقوقي؟

**Gold answer:** لا. تحويل عقد العمل غير المرن إلى أحد أشكال العمل المرن يكون بالاتفاق بين صاحب العمل والعامل، ولا يجوز تحويل صفة العقد إلى عمل مرن أو بالعكس إذا كان ذلك ينتقص من حقوق العامل المنصوص عليها في القانون.

**System answer:** None

**Reviewer finding:** Empty system output with no citations or retrieved evidence. Treat as a technical/API collection failure, not hallucination.

## 9. Main Findings

1. **The RAG system is safer than the baseline.** It correctly abstained on unsupported and out-of-scope questions.

2. **Legal-answer correctness did not improve over the baseline.** Both systems achieved 40% human-reviewed legal correctness on answerable questions.

3. **False abstention is the largest RAG weakness.** The system declined 41 answerable outputs, often with the canonical insufficient-knowledge response.

4. **Citation selection is too broad.** Correct answers frequently returned additional chunks that were unrelated to the claims.

5. **Retrieval ranking sometimes preferred older guides or adjacent topics over the most direct official legal provision.**

6. **Some answers were incomplete even when the correct source was available.** Important conditions, exceptions, fines, or time limits were omitted.

7. **Operational reliability is strong for a prototype.** Only one of 150 RAG requests failed, though tail latency remains high.

## 10. Prioritized Improvement Plan

### Priority 1 — Reduce false abstentions

- Inspect the evidence-sufficiency and confidence gates.
- Separate weak retrieval from generator failure.
- Evaluate thresholds using the held-out dataset rather than changing them from individual examples.
- Preserve correct abstention on the ten unsupported questions.

### Priority 2 — Filter citations

- Return only chunks that directly support claims in the final answer.
- Do not expose every retrieved candidate as a citation.
- Prefer official statutory provisions over secondary guides when both support the answer.

### Priority 3 — Improve retrieval ranking

- Give ranking priority to official, current, and article-specific sources.
- Penalize unrelated chunks even when they share broad labour-law vocabulary.
- Add regression cases for flexible work, leave, dismissal, wages, occupational safety, and Social Security.

### Priority 4 — Improve answer completeness

- Require the generated answer to cover all retrieved legal conditions, exceptions, deadlines, percentages, and penalties relevant to the question.
- Add completeness checks against required points during evaluation.

### Priority 5 — Control tail latency

- Investigate the single 30-second request.
- Add bounded timeout handling and structured timeout diagnostics.
- Track p50, p95, maximum latency, 5xx rate, and timeout rate in future regression runs.

## 11. Final Assessment

Lawz AI JO demonstrates a defensible end-to-end evaluation workflow with a held-out dataset, repeatable multi-seed runs, a baseline comparison, automated retrieval checks, human legal review, abstention evaluation, latency measurement, reliability measurement, and categorized failure analysis.

The RAG system is safer and more correct overall than the BM25 baseline, but it is **not yet ready for high-stakes legal use**. The next iteration should focus on reducing false abstentions, improving citation precision, prioritizing authoritative legal sources, and increasing answer completeness while preserving the current strong abstention safety.

This system provides an initial legal explanation and does not replace advice from a qualified legal professional.
