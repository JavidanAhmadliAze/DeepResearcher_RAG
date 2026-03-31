# Agent Quality and Evaluation Framework

This document defines the metrics used to evaluate the performance and reliability of the DeepResearchAssistant agents.

## 1. Effectiveness (Goal Achievement)
*   **Success Rate**: Percentage of research tasks that result in a completed report.
*   **Accuracy**: Human-in-the-loop (HITL) feedback score on the accuracy of the retrieved information.
*   **Completeness**: Measure of how many aspects of the research brief were covered in the final output.

## 2. Efficiency (Operational Cost)
*   **Token Usage**: Average number of tokens consumed per research task.
*   **Execution Time**: End-to-end latency from research brief submission to final report.
*   **Cost per Task**: Calculated cost based on model (DeepSeek, GPT-4, etc.) prices.

## 3. Robustness (Reliability)
*   **Retry Rate**: Frequency of structured output retries in `model_wrapper.py`.
*   **Error Handling**: Percentage of tasks that fail due to API timeouts or rate limits.
*   **Consistency**: Variance in quality across multiple runs of the same prompt.

## 4. Trustworthiness
*   **Source Attribution**: Ratio of claims in the report supported by a retrieved source.
*   **Hallucination Rate**: Human evaluation of claims not supported by any source.
*   **Safety Compliance**: Adherence to safety and privacy guidelines.

## Langfuse Metrics
We observe these metrics via Langfuse:
- `total_tokens`
- `latency`
- `successful_runs` vs `failed_runs`
- `cost` (if configured)
