# Multi-Agent Framework Selection — AI Roundtable Discussion MVP

> Scope: one Chinese topic + N AI personas with distinct stances → personas discuss
> turn-by-turn until the user stops → record full transcript → summarize. Models are
> called via an OpenAI-compatible endpoint (DeepSeek / relay / custom `base_url` + `api_key`).
> Every claim below is traced to a primary source (official GitHub repo / source file).

## Recommendation (TL;DR)

**Use LangGraph (LangChain) as the orchestration base.**

- It has best-in-class streaming for a web frontend — `.astream(stream_mode="messages")`
  emits LLM tokens token-by-token, and `interrupt()` lets you pause the graph between
  speakers, which maps directly to "personas discuss until the user stops."
- OpenAI-compatible endpoints are a first-class, caveat-free path via
  `ChatOpenAI(base_url=..., api_key=...)` (the same `langchain-openai` client the whole
  ecosystem uses with DeepSeek/vLLM/relays).
- MIT license, very actively maintained, and the core is lightweight/installable
  standalone.

**Runner-up:** AG2 (`ag2ai/ag2`, the actively-maintained AutoGen fork) if you want
round-robin group chat as a *built-in* primitive — but see the maintenance-mode warning
on Microsoft AutoGen below.

---

## Comparison Table

| Framework | OpenAI-compatible endpoint (`base_url`+`api_key`) | Turn-taking / group orchestration | Chinese (hard blockers) | Streaming to web (SSE/WS) | Weight / learning curve | License / maintenance |
|---|---|---|---|---|---|---|
| **AutoGen** (microsoft/autogen) | Yes — `base_url`+`api_key`, but "not tested or guaranteed" for non-OpenAI models; needs `model_info` | **First-class** — `RoundRobinGroupChat`, `SelectorGroupChat`, `SwarmGroupChat` | None | Yes — `run_stream()` + official FastAPI/WebSocket sample | Medium (AgentChat is high-level) | Code **MIT**, docs CC-BY-4.0; **maintenance mode** |
| **AG2** (ag2ai/ag2) | Yes — `OpenAIConfig(model, api_key, ...)`; classic `OAI_CONFIG_LIST` supports `base_url` | **First-class** — `discussion` channel = "round-robin across N agents" (v1.0); `GroupChat`/`GroupChatManager` (classic) | None | Yes (classic `autogen` streaming; MemoryStream in v1.0) | Medium | **Apache-2.0**, very active |
| **CrewAI** | Yes — LiteLLM-based `LLM(base_url=..., api_key=...)` | Weak fit — task-oriented `Crew` (`sequential`/`hierarchical`), not free dialogue | None | Yes (newer) — `StreamFrame` channels incl. token chunks | Medium-heavy (LiteLLM, tiktoken/Rust) | **MIT**, very active |
| **LangGraph** | **Yes** — `ChatOpenAI(openai_api_base alias "base_url", api_key)` | Build-your-own cyclic graph + subgraphs (flexible, more code) | None | **Best-in-class** — `stream_mode="messages"` token streaming + `interrupt()` HITL | Lightweight core, but low-level (more code) | **MIT**, very active |
| **MetaGPT** | Yes — `base_url`+`api_key` in config.yaml | Fixed software-company SOP pipeline (roles), not free discussion | None | No token streaming to web | Medium | MIT, **stale** (last push ~7 mo ago) |
| **CAMEL** | Yes — `ModelPlatformType` + `api_key` (base_url via model config) | 2-agent `RolePlaying` + societies (research-oriented) | None | Limited | Medium | Apache-2.0, active |

---

## Per-Framework Notes (with citations)

### AutoGen — microsoft/autogen

- **Status / license (critical):** The repo is explicitly in **maintenance mode**. The README
  carries a "maintenance mode" badge and a caution block: *"AutoGen is now in maintenance mode.
  It will not receive new features or enhancements and is community managed going forward…
  New users should start with Microsoft Agent Framework."* — https://github.com/microsoft/autogen
- **License nuance:** GitHub's top-level license field reports **CC-BY-4.0**, but the README
  "Legal Notices" clarify that **documentation** is CC-BY-4.0 while **code** is MIT
  (`LICENSE-CODE`). https://github.com/microsoft/autogen#legal-notices
- **Endpoint:** `OpenAIChatCompletionClient(model, api_key, base_url, ...)` where the docstring
  states `base_url` is *"Required if the model is not hosted on OpenAI"*, and *"You can also use
  this client for OpenAI-compatible ChatCompletion endpoints. Using this client for non-OpenAI
  models is not tested or guaranteed."* Non-OpenAI model names also require a `model_info` dict.
  https://github.com/microsoft/autogen/blob/main/python/packages/autogen-ext/src/autogen_ext/models/openai/_openai_client.py
- **Turn-taking:** `RoundRobinGroupChat`, `SelectorGroupChat`, `SwarmGroupChat` are first-class
  team primitives (source dir `python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/`).
- **Streaming:** `agent.run_stream()` (used as `Console(agent.run_stream(...))` in the README), plus
  an official **FastAPI + WebSocket** sample (`python/samples/agentchat_fastapi/`) whose README says
  *"The team follows a round-robin strategy so each agent will take turns to respond."* —
  https://github.com/microsoft/autogen/tree/main/python/samples/agentchat_fastapi

### AG2 — ag2ai/ag2 (the AutoGen fork)

- **Identity:** *"AG2 (formerly AutoGen)"*, Apache-2.0, pushed 2026-08-18 (very active).
  https://github.com/ag2ai/ag2
- **Two packages:** `ag2` (v1.0) introduces a **Network** model (Hub + typed channels); `ag2-classic`
  keeps the `autogen` namespace (`ConversableAgent`, `GroupChat`, `GroupChatManager`,
  `OAI_CONFIG_LIST`). README: *"`pip install ag2` no longer ships the `autogen` import name."*
- **Turn-taking:** v1.0 `discussion` channel is documented as *"round-robin across N agents"* —
  an exact match for a roundtable; classic `GroupChat` is the battle-tested equivalent.
- **Endpoint:** `OpenAIConfig(model="gpt-4o-mini", api_key=...)`; classic supports `base_url`
  through `config_list`/`OAI_CONFIG_LIST`.

### CrewAI — crewAIInc/crewAI

- **License/activity:** MIT, pushed 2026-08-18 (very active). https://github.com/crewAIInc/crewAI
- **Endpoint:** The `LLM` class is LiteLLM-based (LiteLLM is lazy-loaded) and passes `base_url` +
  `api_key` straight to `litellm.completion` (source has `_has_custom_openai_base_url` checking
  `base_url`/`api_base`). https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/llm.py
- **Turn-taking (weak fit):** CrewAI is *task*-oriented: `Crew` with `Process.sequential` /
  `Process.hierarchical` (a manager agent delegates tasks). There is no free-form "everyone takes a
  turn speaking" primitive; a roundtable would have to be shoehorned into tasks or Flows.
- **Streaming (newer):** Documented `StreamFrame` model with channels `llm` (incl. token chunks
  `llm_stream_chunk`), `messages`, `flow`, `tools`; entry points `flow.stream_events()` and
  `Crew(..., stream=True)` → `CrewStreamingOutput`.
  https://github.com/crewAIInc/crewAI/blob/main/docs/edge/en/concepts/streaming.mdx
- **Weight:** Medium-heavy — LiteLLM + pydantic + instructor; README notes `tiktoken` may need a
  Rust/VS C++ toolchain on Windows.

### LangGraph — langchain-ai/langgraph (recommended)

- **License/activity:** MIT, pushed 2026-08-16 (very active). README self-describes as
  *"Low-level orchestration framework for building stateful agents."* https://github.com/langchain-ai/langgraph
- **Endpoint:** Uses LangChain chat models; `ChatOpenAI` exposes
  `openai_api_base: str | None = Field(default=None, alias="base_url")` and `api_key`, with
  in-repo examples like `ChatOpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")` (vLLM /
  LM Studio style) — the standard, caveat-free path for DeepSeek/relays.
  https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py
- **Turn-taking:** No built-in "roundtable" — you build a cyclic `StateGraph` (e.g., a node per
  persona, or one node that selects the next speaker) with the transcript in state. Flexible, but
  more code than AutoGen's group chat.
- **Streaming (best-in-class):** `.stream()` / `.astream()` with `stream_mode`:
  `values | updates | checkpoints | tasks | debug | messages | custom`, where `"messages"`
  *"Emit LLM messages token-by-token together with metadata"*.
  https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/types.py
- **Human-in-the-loop:** `interrupt()` pauses the graph for external input/resume — a clean match
  for "stop the discussion / let the user interject between turns."
- **Weight:** `pip install langgraph`; README notes it *"can be used without LangChain"* (in
  practice you add `langchain-openai` for the model client). Low-level = steeper initial curve.

### MetaGPT — FoundationAgents/MetaGPT

- MIT, but last push 2026-01-21 (stale). Role-based *software-company* SOP pipeline (product
  manager / architect / engineer), not free-form discussion — a poor fit for a roundtable.
  `base_url`+`api_key` supported in config.yaml. https://github.com/FoundationAgents/MetaGPT

### CAMEL — camel-ai/camel

- Apache-2.0, active (pushed 2026-08-14). Research-oriented; core pattern is 2-agent
  `RolePlaying` plus "agent societies" and dataset generation — heavier and less aligned with a
  production roundtable web app than the top candidates. https://github.com/camel-ai/camel

---

## Chinese-language note (all candidates)

None of the frameworks impose a language restriction — they pass through user-defined system
prompts / role definitions and are model-agnostic, so Chinese topics and personas work as long as
the underlying model (e.g., DeepSeek) handles Chinese. All official docs are English-only, which
is a minor friction, not a blocker. (No framework-level language gate found in any of the repos
reviewed.)

---

## Known pitfalls of LangGraph for this use case

1. **You write the turn loop yourself.** LangGraph has no built-in "round-robin group chat."
   You must build a cyclic graph (a "next speaker" node + a per-speaker generation node), keep the
   transcript in `State`, and enforce a max-turn/stop condition. More upfront code than AutoGen's
   `RoundRobinGroupChat`.
2. **Two model clients, two packages.** LangGraph itself doesn't call models — you add
   `langchain-openai` and point `ChatOpenAI(base_url=..., api_key=...)` at DeepSeek/relay. Remember
   the field is named `openai_api_base` (alias `base_url`), not `base_url` alone, in some versions.
3. **Token streaming requires the right stream mode.** Use `.astream(..., stream_mode="messages")`
   to get token-level chunks for SSE; the default `stream_mode="values"` only emits full state per
   step (not per token). Pipe this into a FastAPI `StreamingResponse`/SSE or WebSocket.
4. **"Until the user stops" → `interrupt()` + checkpointer.** `interrupt()` needs a checkpointer
   (in-memory is fine for MVP) so the graph can pause/resume with state persisted between turns.
   Plan the interrupt point explicitly (e.g., after each speaker's turn).
5. **Summarization is a separate step.** Build a final summarization node that reads the transcript
   from state; ensure the transcript accumulation node appends each persona's message with speaker
   labels so the summary can attribute stances correctly.
6. **Concept surface area.** StateGraph, nodes, edges, state schema (`TypedDict`/Pydantic), stream
   modes, and checkpointer are concepts to learn before writing the roundtable loop. For a
   two-persona quick demo this is small; for N dynamic personas, the loop logic grows.
