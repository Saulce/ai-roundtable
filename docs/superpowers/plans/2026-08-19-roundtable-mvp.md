# AI 圆桌讨论 MVP Implementation Plan

> **执行方式：** 本计划是「接口 + 测试」spec。10 个实现任务各自是一个 GitHub issue（label `implementation`，#9–#18），issue 正文 = 该任务的 **Interfaces + 失败测试**，**不含实现代码**。实现阶段用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐 issue 落地（TDD：先写测试跑失败 → 实现 → 跑通过）。本文件是**轻量索引**，只保留全局 spec 与任务链接，不重复 issue 里的接口/测试细节。

**Goal:** 构建一个可运行的 MVP 网页应用：用户输入话题 + 选定若干立场各异的 AI 角色，角色自由发言直到用户停止（手动停止=终止 / 达轮次上限=暂停），全程记录为中文文本，并可生成摘要/总结。

**Architecture:** Python + LangGraph 编排（单循环图：开场陈述 → 选发言人 → 发言 → 循环），FastAPI 提供 REST + SSE 流式接口，SQLite 持久化，原生 HTML/CSS/JS 前端（无构建步骤）。模型走 OpenAI 兼容接口（`ChatOpenAI(base_url=..., api_key=...)`，默认 DeepSeek）。所有 LLM 调用走 async（`ainvoke`/`astream`），保证 FastAPI 事件循环不被阻塞、停止命令可即时生效。

**Tech Stack:** Python 3.11+、LangGraph、langchain-openai、FastAPI + uvicorn、SQLite（标准库 `sqlite3`）、原生前端（`EventSource` SSE + `fetch` REST）、pytest。

**Spec:** 本计划实现的 spec = Wayfinder Map（GitHub issue [#1](https://github.com/Saulce/ai-roundtable/issues/1)）及其 7 张已关闭决策票：框架选型 [#7](https://github.com/Saulce/ai-roundtable/issues/7)、MVP 边界 [#2](https://github.com/Saulce/ai-roundtable/issues/2)、讨论编排模型 [#3](https://github.com/Saulce/ai-roundtable/issues/3)、结束模型 [#4](https://github.com/Saulce/ai-roundtable/issues/4)、角色模型 [#5](https://github.com/Saulce/ai-roundtable/issues/5)、摘要与总结 [#6](https://github.com/Saulce/ai-roundtable/issues/6)、Web 前端与流式交互 [#8](https://github.com/Saulce/ai-roundtable/issues/8)。关键决议已内联到下方 Global Constraints。

## Global Constraints

（以下为 spec 锁定的全局要求，逐条照抄；每个任务的需求隐式包含本节。）

- **编排**：LangGraph，`pip install langgraph`；模型客户端 `langchain-openai` 的 `ChatOpenAI(base_url=..., api_key=...)`，OpenAI 兼容接口，默认 DeepSeek（`https://api.deepseek.com/v1`）。
- **发言机制**：逐轮判定单循环 `选发言人 → 发言 → 追加转录 → 回到选发言人`；选发言人节点永远输出恰好一个下一发言人（不返回「无人」）；连续多轮选同一人即自然涌现「想发几句就发几句」；**无主持人角色**，控场在编排层。
- **内部结构**：开场陈述轮（每个角色按用户选定顺序各发一条初始立场陈述，只表立场不攻击）+ 纯自由对话（无阶段标记）。
- **卡住**：选发言人节点输出 `stalled: bool` 停滞信号；停滞时指定「沉默最久/参与最少」的角色推进。
- **上下文**：每个发言节点可见 = 话题 + 全部开场陈述（永久在场）+ 最近 15 条正文；`N=15` 为可配置常量。
- **结束控制**：手动停止 = **终止**（最高优先级，立即生效，触发全场总结，不可继续）；轮次上限默认 **15 轮**（发布话题时可自定义为任意 N、可关闭=仅手动停止，讨论开始后不可改）= **暂停**（触发本轮摘要，每次「继续」再给 N 轮）；**共识自动判定永久不做**。
- **角色（persona）**：预设套件 5 个（好为人师者/杠精/中立质疑者/领域专家/理想主义者，默认勾选前三）+ 用户自定义；数量默认 3、可调 2–6；字段 = 名字/立场/说话风格必填 + 专业背景可选；全透明共享上下文；所有角色同模型同参数。
- **摘要/总结**：编排层独立总结节点（非讨论角色），按 mode 取 prompt 模板；摘要（暂停，轻：本段焦点/各方本段要点/本段分歧点/轻量立场变动提示）、总结（终止，全：脉络概述/各方核心观点/核心分歧点/未决问题/**开场 vs 结束立场对比表**）；**均不下结论**；结构化 Markdown；总结含对比表，列 = 角色/开场立场基线/结束立场/漂移。
- **立场数据来源**：开场基线 = persona 立场字段 + 开场陈述轮；结束立场 = 总结节点读全场转写推断。
- **传输**：**SSE 推 token + REST POST 叫停/继续，不上 WebSocket**。前端 `EventSource` + `fetch`。
- **持久化**：SQLite，存本次转写 + 摘要/总结，可回看历史场次。
- **语言**：讨论全中文。
- **Out of scope**（不实现）：长期记忆（v1.1）、上下文窗口完整管理（v1.1，MVP 用「开场永久 + 最近 15 条」截断）、共识自动判定（永久）、讨论模式/协作解题（后续版本）、多房间、账号、语音、移动端、RAG、游戏化。

---

## File Structure

```
ai-roundtable/
├── app/
│   ├── __init__.py          # 空
│   ├── config.py            # Config（env 配置）
│   ├── llm.py               # get_llm(config) -> ChatOpenAI
│   ├── personas.py          # Persona 模型 + PRESET_PERSONAS + validate_personas + persona_by_name
│   ├── state.py             # DiscussionState (TypedDict)
│   ├── prompts.py           # build_opening/speak/select_speaker/summary prompt
│   ├── nodes.py             # async 核心函数：generate_opening/astream_speech/select_next_speaker/parse_speaker_choice/generate_summary
│   ├── graph.py             # build_graph(llm) -> CompiledStateGraph（含 should_end 路由）
│   ├── storage.py           # Storage（SQLite 持久化）
│   ├── sessions.py          # SessionManager（运行中讨论生命周期 + SSE 事件编排 + 暂停/继续/终止）
│   └── main.py              # FastAPI app + REST/SSE 端点 + 静态前端挂载
├── frontend/
│   ├── index.html           # 两视图（发起页 / 讨论页）
│   ├── app.js               # SSE 消费 + REST 调用 + 渲染
│   └── style.css            # 三栏布局 + 金色锚点卡片 + overlay
├── tests/
│   ├── conftest.py          # FakeLLM 夹具（ainvoke/astream）
│   ├── test_config.py
│   ├── test_personas.py
│   ├── test_prompts.py
│   ├── test_nodes.py
│   ├── test_graph.py
│   ├── test_storage.py
│   ├── test_sessions.py
│   ├── test_api.py
│   ├── test_frontend.py
│   └── test_e2e.py
├── requirements.txt
├── .env.example
└── README.md
```

**职责边界**：`nodes.py` 是纯函数（给定 LLM + 输入 → 输出字符串/解析结果），不依赖 LangGraph；`graph.py` 只做「把 nodes 焊进 StateGraph + 条件路由」；`sessions.py` 只做「运行中讨论生命周期 + SSE 事件编排 + 暂停/继续/终止 + 从 storage 重建状态」；`main.py` 只做「HTTP 层」。每层独立测试。

**关键设计约定（实现前必读）**：
- LangGraph 的 `astream(input, ...)` 不会回写传入的 `input` dict —— 图在内部累积状态，`input` 保持不变。所以「继续」需要把上一段结束后的状态重建出来再作为下一段的输入。本计划用 **SQLite 作为转录的单一事实源**：`sessions` 逐事件持久化，段结束时从 storage 重建累计状态。
- `transcript` = **仅自由发言**（不含开场）；`opening_statements` = 仅开场陈述（永久在场，单独传给 prompt）。开场陈述轮全部先发生、自由发言在后，故「全场记录 = opening_statements + transcript」按序拼接即正确。
- 轮次上限 N 是「每段 N 轮」；图内 `max_turns` 是「本段累计预算」，由 session 在每次「继续」时设为 `turn_count + N`；`_per_segment` 保存原始 N。

---

## 实现任务索引（GitHub issues）

每个 issue = 该任务的 **Interfaces + 失败测试**（`implementation` 标签）。按序执行：

- [Task 1: 项目脚手架 + 配置 + LLM 工厂](https://github.com/Saulce/ai-roundtable/issues/9) — `Config` + `get_llm` + `FakeLLM` 夹具 + requirements/.env
- [Task 2: Persona 模型 + 预设套件](https://github.com/Saulce/ai-roundtable/issues/10) — `Persona`/`PRESET_PERSONAS`/`validate_personas`/`persona_by_name`
- [Task 3: 状态模式 + Prompt 模板](https://github.com/Saulce/ai-roundtable/issues/11) — `DiscussionState` + 4 个 prompt builder + `CONTEXT_WINDOW`
- [Task 4: 节点核心函数（纯逻辑，async）](https://github.com/Saulce/ai-roundtable/issues/12) — opening/speech/speaker-select/summary + 容错 JSON
- [Task 5: LangGraph 图组装 + 循环 + 轮次上限路由](https://github.com/Saulce/ai-roundtable/issues/13) — `build_graph`/`should_end` + 事件约定
- [Task 6: SQLite 持久化](https://github.com/Saulce/ai-roundtable/issues/14) — `Storage`
- [Task 7: SessionManager（停止/继续/暂停编排）](https://github.com/Saulce/ai-roundtable/issues/15) — run/stop/continue + 事件转发
- [Task 8: FastAPI + SSE 端点](https://github.com/Saulce/ai-roundtable/issues/16) — REST + SSE + 静态挂载
- [Task 9: 前端（发起页 + 三栏讨论页）](https://github.com/Saulce/ai-roundtable/issues/17) — 两视图 SPA
- [Task 10: 端到端集成 + README](https://github.com/Saulce/ai-roundtable/issues/18) — e2e 冒烟 + 快速开始

---

## 完成定义（Done）

全部 10 个 issue 落地后，MVP 应满足：输入话题 + 选 2–6 个角色 → 发起 → 开场陈述轮（金色锚点卡片）→ 角色自由发言（token 流式上屏，连续多轮选同一人可连发）→ 卡住时强制指定沉默最久者 → 达轮次上限暂停（分段摘要 + 可继续）→ 手动停止终止（全场总结 overlay 含立场漂移对比表）→ 转写与摘要/总结落 SQLite 可回看。全部 `pytest -v` 通过。
