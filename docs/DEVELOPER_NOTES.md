# Developer notes — OpenAI references for SnapDish

Curated links and short summaries for voice/realtime, agents, function calling, ChatGPT Apps, and evals. Use these when extending Chef Marco, adding realtime voice, or building ChatGPT or mobile experiences.

---

## Voice & Realtime API

SnapDish currently uses the **Agents SDK voice pipeline** (STT → agent → TTS) via `POST /v1/voice` and the CLI `voice_assistant.py`. For **lower-latency, true speech-to-speech** in the mobile app, consider the **Realtime API**.

| Topic | Link | When to use |
|-------|------|--------------|
| **Realtime API overview** | [Realtime API](https://developers.openai.com/api/docs/guides/realtime) | Building voice agents with gpt-realtime (WebRTC in browser, WebSocket on server). |
| **Voice agents (Agents SDK)** | [Voice agents quickstart (TypeScript)](https://openai.github.io/openai-agents-js/guides/voice-agents/quickstart/) | RealtimeSession + WebRTC in the browser; same “voice agent” idea as our Python pipeline. |
| **Realtime developer notes** | [Introducing gpt-realtime](https://openai.com/index/introducing-gpt-realtime/) + [Realtime docs](https://platform.openai.com/docs/guides/realtime) | GA model, connection methods (WebRTC / WebSocket / SIP), **beta → GA migration**, idle timeouts, truncation, async function calling, hosted prompts, sideband connections. |

**Takeaways for SnapDish (mobile-first):**

- **Realtime API** = low-latency speech-to-speech; connect via **WebRTC** (browser/client) or **WebSocket** (server). Use **ephemeral keys** (`POST /v1/realtime/client_secrets`) in the client; keep API key on the server.
- **Session config:** `session.type` = `"realtime"` (speech-to-speech) or `"transcription"` (transcription only). Set `audio.output.voice` (e.g. `marin`, `cedar`), `instructions`, and optionally `prompt.id` (hosted prompts).
- **Idle timeouts:** `server_vad.idle_timeout_ms` so the model can say “Are you still there?” after silence.
- **Long sessions:** 60 min max; truncation when context fills; optional `retention_ratio` for cache-friendly truncation.
- **Mobile:** Use WebRTC from your client (or a WebSocket proxy from your backend) and respect GA event names (e.g. `response.output_audio.delta` instead of `response.audio.delta`).

---

## Agents: Skills, Shell, Compaction

For **long-running or more capable agents** (e.g. multi-step cooking workflows, research, file/output generation), these primitives help.

| Topic | Link | When to use |
|-------|------|--------------|
| **Shell + Skills + Compaction** | [Blog: Tips for long-running agents](https://developers.openai.com/blog/skills-shell-tips) | **Skills** = versioned playbooks (SKILL.md) the model can load; **Shell** = hosted or local terminal for install/run/write; **Compaction** = keep long runs under context limits. Use together for repeatable, executable workflows. |
| **Skills** | [Skills docs](https://developers.openai.com/api/docs/guides/tools-skills) | Encode procedures and templates in a skill; describe “when to use / when not to use” and add negative examples to improve routing. |
| **Compaction** | [Run and scale / Compaction](https://developers.openai.com/api/docs/guides/compaction) | When conversation history grows, use server-side compaction or `/responses/compact` so the agent doesn’t hit context limits. |

**Takeaways:**

- **Skills:** Write skill **descriptions** like routing logic (when to use / when not); put **templates and examples inside the skill** so they’re only loaded when the skill runs.
- **Shell:** Use for “install → fetch → write artifact” or for skills that need to run commands; treat `/mnt/data` as the handoff path for outputs.
- **Security:** Skills + open network = high risk; use **allowlists** (org-level and request-level) and **domain_secrets** for authenticated calls.
- **Determinism:** When you need a fixed workflow, tell the model explicitly: “Use the &lt;skill name&gt; skill.”

---

## Function calling (tool calling)

**Function calling** lets the model use **tools** you define: request data or actions via a **tool call**, your app runs the logic and returns a **tool call output**, then the model produces a final reply. SnapDish already uses tools in the voice agent (e.g. `get_nutrition_estimate`, `find_nearby_stores`, `get_account_info`, web search) and can use them in the Responses API for `/v1/analyze` (e.g. vision + actions).

| Topic | Link | When to use |
|-------|------|--------------|
| **Function calling guide** | [Function calling](https://developers.openai.com/api/docs/guides/function-calling) | End-to-end flow, defining functions (JSON schema), handling calls, tool_choice, strict mode, streaming, custom tools, CFG (Lark/regex). |
| **Built-in tools** | [Tools overview](https://developers.openai.com/api/docs/guides/tools) | Web search, code interpreter, MCP, etc. |

**The tool-calling flow (5 steps):**

1. Request the model with a list of **tools** it may call.
2. Receive a **tool call** from the model (`type: "function_call"`, `call_id`, `name`, `arguments` JSON).
3. Execute your code using the tool call input.
4. Send a second request with **tool call output** (`type: "function_call_output"`, `call_id`, `output` string or image/file array).
5. Receive the final text (or more tool calls). For reasoning models, include any reasoning items when you resubmit with tool outputs.

**Function vs custom vs built-in:**

- **Function tools** — JSON schema for parameters; model passes structured arguments; use for APIs, DB lookups, refunds, etc.
- **Custom tools** — Free-form text input/output; optional **context-free grammar** (Lark or regex) to constrain the model’s input. Use when you want to avoid wrapping in JSON or need a custom format.
- **Built-in tools** — Web search, code interpreter, MCP; see the tools overview.

**Best practices:**

- **Clear names and descriptions:** Describe the purpose of the function and each parameter (and format); use the system prompt to say when (and when not) to use each function.
- **Strict mode:** Set `strict: true` so calls adhere to the schema; requires `additionalProperties: false` and all properties in `required` (use `null` in `type` for optional fields).
- **Offload from the model:** Don’t make the model fill arguments you already know (e.g. pass `order_id` in code, not as a param). Combine functions that are always called in sequence.
- **Token usage:** Functions are injected into context and count as input tokens; keep the number of functions and description length manageable (&lt;20 functions is a soft target).
- **Parallel calls:** The model may call multiple tools in one turn. Set `parallel_tool_calls: false` to allow at most one call per turn (required when using built-in tools).

**tool_choice:**

- `"auto"` — Model decides (default).
- `"required"` — At least one tool must be called.
- `{"type": "function", "name": "get_weather"}` — Force exactly that function.
- `{"type": "allowed_tools", "mode": "auto", "tools": [...]}` — Restrict to a subset (helps with prompt caching).
- `"none"` — No tools.

**Streaming:** With `stream: true`, use `response.output_item.added` for each function call, then `response.function_call_arguments.delta` for argument chunks and `response.function_call_arguments.done` for the full call.

**Custom tools + CFG:** Use the `grammar` (Lark or regex) on a custom tool to constrain the model’s text input. Keep grammars simple; use one bounded terminal for “free text between anchors” rather than splitting across rules. Regex uses Rust regex syntax, not Python `re`.

**Where SnapDish uses tools:** `backend/snapdish/voice_agent.py` (Knowledge, Account, Search agents), `backend/snapdish/tools.py` (store/nutrition stubs). For vision + function calling (e.g. image → choose action), see STRUCTURE.md “Vision + function calling” and the [vision + function calling cookbook](https://developers.openai.com/cookbook/examples/multimodal/using_gpt4_vision_with_function_calling).

**Vision + function calling (cookbook pattern):**

- **Image → tool/action:** Send the image in the user message (`image_url` with `data:image/jpeg;base64,...` or HTTPS URL). Define tools or a structured `response_model` (e.g. `RefundOrder | ReplaceOrder | EscalateToAgent`). The model analyzes the image and returns the chosen action and params (rationale, image_description, message). Example: delivery exception support — damaged → refund, wet → replace, normal → escalate. Use **instructor** with `instructor.from_openai(OpenAI(), mode=instructor.Mode.PARALLEL_TOOLS).chat.completions.create(..., response_model=Iterable[RefundOrder|ReplaceOrder|EscalateToAgent], messages=[..., { "role": "user", "content": [{ "type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{base64_img}" } }] }])`.
- **Image → structured extract:** For OCR-style or diagram extraction (e.g. org chart → list of employees with name, role, manager), use a single Pydantic `response_model` (e.g. `EmployeeList`) and one user message with the image; no tools required. Same message shape: `content: [{ "type": "image_url", "image_url": { "url": "..." } }]`.
- **SnapDish:** To add “image → action” (e.g. dish photo → `suggest_recipe` | `find_stores` | `escalate`), add an endpoint that accepts image + optional text, calls a vision-capable model with tools or structured output, and returns the chosen action; then run the action server-side. Cookbook: [GPT-4o Vision with function calling](https://developers.openai.com/cookbook/examples/multimodal/using_gpt4_vision_with_function_calling).

---

## Cost & model choice: Flex and reasoning

**Flex processing** — Lower cost for Responses (or Chat) in exchange for slower response times and possible **429 Resource Unavailable**. Set `service_tier: "flex"` in the request. Ideal for non-urgent work (evals, enrichment, async). Increase **timeout** (e.g. 15 min in Python: `client.with_options(timeout=900.0).responses.create(...)`). On 429, retry with exponential backoff or retry with `service_tier: "auto"` (standard pricing). [Flex processing](https://developers.openai.com/api/docs/guides/cost-optimization) · [Pricing](https://developers.openai.com/api/docs/pricing).

**Reasoning models (o-series) vs GPT:**

- **GPT models** — Faster, lower cost; good for well-defined tasks and high throughput (e.g. triage, simple extraction, chat).
- **o-series (o1, o3, o4-mini)** — Better for complex planning, ambiguity, multistep reasoning, visual reasoning (o1), and “needle in haystack” over long documents. Use as the **planner**; use GPT as the **doer** for specific steps.
- **Responses API + function calling:** Use `store: true` and pass **reasoning items** (via `previous_response_id` or by re-attaching output items) so the model doesn’t restart reasoning on each function round-trip; better accuracy and lower reasoning token usage. Chat Completions is stateless and does not include reasoning in context.
- **Prompting:** Keep instructions simple and direct; avoid “think step by step” (reasoning is internal). Use delimiters and be specific about success criteria. [Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices) · [Reasoning guide](https://developers.openai.com/api/docs/guides/reasoning).

---

## ChatGPT Apps (15 lessons)

Relevant if you build a **ChatGPT App** (Apps SDK, MCP, widgets inside ChatGPT) or any **agentic UI** where the model and the user share context.

| Topic | Link | When to use |
|-------|------|--------------|
| **15 lessons building ChatGPT Apps** | [Blog: 15 lessons](https://developers.openai.com/blog/15-lessons-building-chatgpt-apps) | **Context asymmetry** (user / UI / model each have partial knowledge); what to share with the model vs. widget; lazy-loading vs. front-loading; `setWidgetState` and `data-llm`; display modes (inline, PiP, fullscreen); CSPs; tool annotations and visibility. |

**Takeaways:**

- **Not all context should be shared:** Use different tool output fields for “for model + widget” vs “widget only” (e.g. `_meta`).
- **Front-load data** in tool responses when the model needs it; avoid extra tool round-trips for every user click.
- **Model visibility:** Use `setWidgetState` (or declarative `data-llm`) so the model knows what the user is looking at (e.g. which product).
- **UI:** Support inline, PiP, and fullscreen; account for safe zones (e.g. close button on mobile).
- **CSPs:** Declare `connectDomains`, `resourceDomains`, `frameDomains`, `redirectDomains` correctly so the app works in production.

---

## Evals for agent skills

Use when you add **skills** or **reusable procedures** and want to test that the agent triggers and behaves correctly.

| Topic | Link | When to use |
|-------|------|--------------|
| **Testing Agent Skills with Evals** | [Blog: Evals for skills](https://developers.openai.com/blog/eval-skills) | Define **success** (outcome, process, style, efficiency); create a small **prompt set** (positive + negative cases); run the agent, capture **JSONL trace**; add **deterministic checks** (e.g. “did it run npm install?”) and **rubric-based grading** with `--output-schema`. |

**Takeaways:**

- **Define success first:** Outcome, process, style, efficiency; keep the list small and checkable.
- **Prompt set:** Include explicit skill invocation, implicit (description-only), contextual, and **negative** (“don’t trigger here”) cases.
- **Deterministic graders:** Use `codex exec --json` (or your runner’s equivalent), parse events, check for expected commands/outputs.
- **Qualitative checks:** Use a second, read-only run with `--output-schema` to grade style/conventions in a comparable way.

---

## Quick reference

| I want to… | Start here |
|------------|------------|
| Add **realtime speech-to-speech** in the mobile app | Realtime API docs; WebRTC or WebSocket; ephemeral keys; GA migration. |
| Add **skills** or **shell** to Chef Marco (long-running workflows) | [Skills + Shell + Compaction blog](https://developers.openai.com/blog/skills-shell-tips). |
| Define or refine **tools** (function/custom) for the model | [Function calling guide](https://developers.openai.com/api/docs/guides/function-calling); strict mode, tool_choice, streaming. |
| Build a **ChatGPT App** (widgets, tools, context) | [15 lessons](https://developers.openai.com/blog/15-lessons-building-chatgpt-apps). |
| **Test** that a skill triggers and follows steps | [Evals for skills](https://developers.openai.com/blog/eval-skills). |
| Tune **realtime** prompts and session config | [Realtime prompting guide](https://developers.openai.com/api/docs/guides/realtime-models-prompting); Realtime playground. |
| **Lower cost** for many analyze requests | **Batch API:** 50% discount, 24h SLA — use `backend/scripts/batch_analyze.py` with a JSONL file. Or `POST /v1/analyze/batch` for same-request batching (no discount). [Batch guide](https://platform.openai.com/docs/guides/batch). |
| **Vision + function calling** (image → action or extract) | Cookbook: image in user message + tools or `response_model`; instructor or Responses API. [GPT-4o Vision with function calling](https://developers.openai.com/cookbook/examples/multimodal/using_gpt4_vision_with_function_calling). |
| **Lower cost, non-urgent** (evals, enrichment) | **Flex:** `service_tier: "flex"`; increase timeout; handle 429 with backoff or fallback to standard. [Flex](https://developers.openai.com/api/docs/guides/cost-optimization). |
| **Complex planning vs speed/cost** | **Reasoning (o-series)** for ambiguity, multistep, visual reasoning; **GPT** for fast execution. Use Responses API with `store: true` and pass reasoning items for best function-calling. [Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices). |
| **Prompting & evals tooling** | Libraries (Guidance, LangChain, Haystack), evals (OpenAI Evals, Prompttools, YiVal), and guides — see [PROMPTING_RESOURCES.md](PROMPTING_RESOURCES.md). |

---

## Where this lives

- **docs/DEVELOPER_NOTES.md** — This file.
- **backend/README.md** — Points to this doc for voice and agents.
- **STRUCTURE.md** — Lists this file in the docs tree.
