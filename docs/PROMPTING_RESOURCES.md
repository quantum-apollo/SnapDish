# Prompting & LLM resources

Curated list of tools, libraries, guides, and papers for improving prompts and LLM-based apps. Use when tuning Chef Marco, adding evals, or building agent flows.

---

## Prompting libraries & tools (alphabetical)

| Resource | Description |
|----------|-------------|
| [Arthur Shield](https://www.arthur.ai/get-started) | Paid: toxicity, hallucination, prompt injection detection. |
| [Baserun](https://baserun.ai/) | Paid: testing, debugging, monitoring LLM apps. |
| [Chainlit](https://docs.chainlit.io/overview) | Python library for chatbot UIs. |
| [Embedchain](https://github.com/embedchain/embedchain) | Python: manage and sync unstructured data with LLMs. |
| [FLAML](https://microsoft.github.io/FLAML/docs/Getting-Started/) | Microsoft: auto ML — model/hyperparameter selection. |
| [Guidance](https://github.com/microsoft/guidance) | Microsoft: Handlebars-style templating for generation, prompting, control flow. |
| [Haystack](https://github.com/deepset-ai/haystack) | Open-source LLM orchestration (Python), production-ready apps. |
| [HoneyHive](https://honeyhive.ai) | Enterprise: evaluate, debug, monitor LLM apps. |
| [LangChain](https://github.com/hwchase17/langchain) | Python/JS: chain prompts and tools. |
| [LiteLLM](https://github.com/BerriAI/litellm) | Python: call LLM APIs with a consistent interface. |
| [LlamaIndex](https://github.com/jerryjliu/llama_index) | Python: augment LLM apps with data. |
| [LMQL](https://lmql.ai) | Language for LLM interaction: typed prompting, control flow, constraints, tools. |
| [OpenAI Evals](https://github.com/openai/evals) | Open-source: evaluate task performance of models and prompts. |
| [Outlines](https://github.com/normal-computing/outlines) | Python: constrain generation and simplify prompting. |
| [Parea AI](https://www.parea.ai) | Debug, test, monitor LLM apps. |
| [Portkey](https://portkey.ai/) | Observability, model management, evals, security for LLM apps. |
| [Promptify](https://github.com/promptslab/Promptify) | Python: use LMs for NLP tasks. |
| [PromptPerfect](https://promptperfect.jina.ai/prompts) | Paid: test and improve prompts. |
| [Prompttools](https://github.com/hegelai/prompttools) | Open-source: test and evaluate models, vector DBs, prompts. |
| [Scale Spellbook](https://scale.com/spellbook) | Paid: build, compare, ship LLM apps. |
| [Semantic Kernel](https://github.com/microsoft/semantic-kernel) | Microsoft: prompt templating, function chaining, memory, planning (Python/C#/Java). |
| [Vellum](https://www.vellum.ai/) | Paid: experiment, evaluate, deploy LLM apps. |
| [Weights & Biases](https://wandb.ai/site/solutions/llmops) | Paid: track training and prompt experiments. |
| [YiVal](https://github.com/YiVal/YiVal) | Open-source: tune and evaluate prompts, retrieval, model params; datasets and evolution strategies. |

**SnapDish-relevant:** For evals and skill testing, see **docs/DEVELOPER_NOTES.md** (Evals for agent skills) and **OpenAI Evals** / **Prompttools** / **YiVal**. For orchestration and chaining, **LangChain**, **Haystack**, or **Semantic Kernel** can sit in front of the Responses API.

---

## Prompting guides

| Resource | Description |
|----------|-------------|
| [Brex Prompt Engineering Guide](https://github.com/brexhq/prompt-engineering) | Intro to LMs and prompt engineering. |
| [learnprompting.org](https://learnprompting.org/) | Introductory course on prompt engineering. |
| [Lil'Log Prompt Engineering](https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/) | Literature review (OpenAI researcher, March 2023). |
| [OpenAI Cookbook: Techniques to improve reliability](https://developers.openai.com/cookbook/articles/techniques_to_improve_reliability) | Techniques for more reliable prompting (Sep 2022). |
| [promptingguide.ai](https://www.promptingguide.ai/) | Guide with many prompting techniques. |
| [Xavi Amatriain: Prompt Engineering 101](https://amatriain.net/blog/PromptEngineering) & [202 Advanced](https://amatriain.net/blog/prompt201) | Short intro and advanced methods (incl. CoT). |

---

## Video courses

| Resource | Description |
|----------|-------------|
| [Andrew Ng — ChatGPT Prompt Engineering for Developers](https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/) | Short course on prompt engineering. |
| [Andrej Karpathy — Let's build GPT](https://www.youtube.com/watch?v=kCc8FmEb1nY) | ML foundations of GPT. |
| [DAIR.AI — Prompt Engineering](https://www.youtube.com/watch?v=dOxUroR57xs) | ~1 hour on prompt techniques. |
| [Scrimba — Assistants API](https://scrimba.com/learn/openaiassistants) | ~30 min on Assistants API. |

---

## Papers (reasoning & advanced prompting)

| Paper | Main idea |
|-------|-----------|
| [Chain-of-Thought Prompting (2022)](https://arxiv.org/abs/2201.11903) | Few-shot “think step by step” improves reasoning (e.g. GSM8K 18%→57%). |
| [Self-Consistency (2022)](https://arxiv.org/abs/2203.11171) | Voting over multiple CoT outputs improves accuracy further. |
| [Tree of Thoughts (2023)](https://arxiv.org/abs/2305.10601) | Search over trees of reasoning steps helps creative and crossword tasks. |
| [Language Models are Zero-Shot Reasoners (2022)](https://arxiv.org/abs/2205.11916) | “Think step by step” in zero-shot improves math (e.g. 13%→41%). |
| [ReAct (2023)](https://arxiv.org/abs/2210.03629) | Alternate **Re**asoning and **Act**ing (tools/env) for better task performance. |
| [Reflexion (2023)](https://arxiv.org/abs/2303.11366) | Retry with memory of failures improves later attempts. |
| [Multiagent Debate (2023)](https://arxiv.org/abs/2305.14325) | Debates between multiple agents improve benchmarks (e.g. 77%→85% on math). |

**Note:** For **reasoning models** (o-series), see **docs/DEVELOPER_NOTES.md** — avoid explicit “think step by step” in prompts; keep instructions simple and direct.

---

## Where this lives

- **docs/PROMPTING_RESOURCES.md** — This file.
- **docs/DEVELOPER_NOTES.md** — Evals, function calling, reasoning best practices, Realtime; links here for prompting/evals tooling.
