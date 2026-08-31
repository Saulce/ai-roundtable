# ai-roundtable

AI 圆桌讨论：几个 AI 角色围绕你给的一个话题各抒己见，直到得出答案（或由你随时叫停），并支持讨论文本的摘要/总结。

## 快速开始

1. 创建虚拟环境并安装依赖：

   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS / Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 配置 `.env`（从模板复制，填入你的 API key）：

   ```bash
   cp .env.example .env
   ```

   必填项 `ROUNDTABLE_API_KEY`；其余可选，默认走 DeepSeek 的 OpenAI 兼容接口
   （`base_url` / `model` 见 `.env.example`）。

3. 启动服务：

   ```bash
   uvicorn app.main:app --reload
   ```

4. 打开 <http://localhost:8000>，发起一场圆桌讨论。

## 架构

- `app/main.py` — FastAPI 入口：REST（创建/列表/详情）+ SSE 流式转发 + 静态挂载前端。
- `app/sessions.py` — `SessionManager` 生命周期编排：create / run / stop / continue_，逐事件落库。
- `app/graph.py` + `app/nodes.py` — LangGraph 单循环讨论图与节点纯函数：开场 → 选发言人 → 自由发言 →（达轮次上限暂停 | 继续）。
- `app/prompts.py` — 各节点的 Prompt 模板（开场 / 选人 / 发言 / 摘要 / 总结）。
- `app/personas.py` — 角色模型与预设套件。
- `app/storage.py` — SQLite 持久化：讨论、转写消息、摘要/总结。
- `app/config.py` + `app/llm.py` — 环境变量配置与 OpenAI 兼容 LLM 工厂。
- `frontend/` — 两视图 SPA：发起页（话题 + 角色）与三栏讨论页（角色 / 聊天流 / 立场漂移），SSE 实时流式。

## 测试

```bash
pytest -v
```

覆盖：配置、角色、Prompt、节点、LangGraph 图、SessionManager、SQLite 存储、REST/SSE API、
前端静态资源，以及一条端到端冒烟（发起 → 流式 → 暂停 → 停止 → 回看）。

## 规格与计划

- [Wayfinder Map](https://github.com/Saulce/ai-roundtable/issues/1) — 全部设计与决策票。
- [框架调研](docs/research/framework-selection.md) — 技术选型（LangGraph）。
- [实现计划](docs/superpowers/plans/2026-08-19-roundtable-mvp.md)。
