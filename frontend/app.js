/* AI 圆桌讨论 · 前端逻辑
   决议来源：Wayfinder Map #1 决策票 #8；spec：Task 9（issue #17）。
   传输：EventSource 消费 SSE（opening/token/message/paused/terminated/error）+ fetch REST（stop/continue）。
   安全：所有动态文本经 textContent 写入，不做 innerHTML 拼接，防 XSS。 */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // 角色视觉（按预设顺序索引分配，稳定可复用）
  const EMOJI = ["📚", "🪓", "❓", "🎓", "🌟"];
  const COLORS = ["#5b6cff", "#e5534b", "#2c9e6b", "#e08a1e", "#8a4fd3"];

  const state = {
    personas: [],           // GET /api/personas 返回的预设
    selected: new Set(),    // 选中的角色下标
    discussionId: null,
    topic: "",
    maxTurns: 15,           // 0 = 仅手动停止
    turns: 0,               // 自由发言条数（开场不计）
    es: null,               // 当前 EventSource
  };

  /* ---------- 工具 ---------- */

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function personaIndex(name) {
    const i = state.personas.findIndex((p) => p.name === name);
    return i >= 0 ? i : 0;
  }
  function styleOf(name) {
    const i = personaIndex(name);
    return { color: COLORS[i % COLORS.length], emoji: EMOJI[i % EMOJI.length] };
  }
  function stanceOf(name) {
    const p = state.personas.find((x) => x.name === name);
    return p ? p.stance : "";
  }

  function scrollToBottom() {
    const tl = $("#timeline");
    tl.scrollTop = tl.scrollHeight;
  }

  function showToast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.hidden = true; }, 3200);
  }

  function showError(msg) {
    const e = $("#setupError");
    e.textContent = msg;
    e.hidden = false;
  }

  function switchView(view) {
    $("#setup-view").hidden = view !== "setup";
    $("#discuss-view").hidden = view !== "discuss";
  }

  function updateRounds() {
    const manual = state.maxTurns <= 0;
    $("#roundsInfo").textContent = manual
      ? `仅手动停止 · 已发言 ${state.turns} 条`
      : `第 ${state.turns}/${state.maxTurns} 轮`;
  }

  /* ---------- 发起页 ---------- */

  async function loadPersonas() {
    try {
      const r = await fetch("/api/personas");
      if (!r.ok) throw new Error("加载预设角色失败");
      state.personas = (await r.json()).personas || [];
      state.personas.slice(0, 3).forEach((_, i) => state.selected.add(i)); // 默认勾选前三
      renderChips();
    } catch (e) {
      showError(e.message);
    }
  }

  function renderChips() {
    const wrap = $("#roleChips");
    wrap.innerHTML = "";
    state.personas.forEach((p, i) => {
      const chip = el("span", "chip" + (state.selected.has(i) ? " on" : ""), `${EMOJI[i % EMOJI.length]} ${p.name}`);
      chip.title = p.stance;
      chip.addEventListener("click", () => {
        if (state.selected.has(i)) state.selected.delete(i);
        else state.selected.add(i);
        renderChips();
      });
      wrap.appendChild(chip);
    });
    updateRoleCount();
  }

  function updateRoleCount() {
    const n = state.selected.size;
    $("#roleCount").textContent = `已选 ${n} 个角色`;
    $("#goBtn").disabled = n < 2; // 少于 2 禁用发起
  }

  async function startDiscussion() {
    const topic = $("#topicInput").value.trim();
    if (!topic) return showError("请输入话题");
    if (state.selected.size < 2) return showError("至少选择 2 个角色才能发起");
    const personas = [...state.selected].sort((a, b) => a - b).map((i) => state.personas[i]);
    const manual = $("#manualStop").checked;
    const maxTurns = manual ? 0 : Math.max(1, parseInt($("#maxTurns").value, 10) || 15);
    try {
      const r = await fetch("/api/discussions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, personas, max_turns: maxTurns }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        return showError(err.detail || "发起讨论失败");
      }
      const data = await r.json();
      enterDiscussion(data.id, topic, personas, maxTurns);
    } catch (e) {
      showError("网络错误：" + e.message);
    }
  }

  /* ---------- 讨论页 ---------- */

  function enterDiscussion(id, topic, personas, maxTurns) {
    state.discussionId = id;
    state.topic = topic;
    state.maxTurns = maxTurns;
    state.turns = 0;
    switchView("discuss");
    $("#discussTitle").textContent = `AI 圆桌 · ${topic}`;
    $("#discussTopic").textContent = topic;
    $("#timeline").innerHTML = "";
    $("#summaryBox").innerHTML = "";
    $("#summaryContent").innerHTML = "";
    $("#summaryOverlay").classList.remove("show");
    renderRoleList(personas);
    renderDrift(personas);
    updateRounds();
    openStream();
  }

  function renderRoleList(personas) {
    const wrap = $("#roleList");
    wrap.innerHTML = "";
    personas.forEach((p) => {
      const s = styleOf(p.name);
      const row = el("div", "role");
      const dot = el("span", "role-dot");
      dot.style.background = s.color;
      row.append(dot, el("span", "name", `${s.emoji} ${p.name}`), el("span", "stance", p.stance));
      wrap.appendChild(row);
    });
  }

  function renderDrift(personas) {
    const wrap = $("#driftList");
    wrap.innerHTML = "";
    wrap.appendChild(el("div", "hint", "开场立场基线（锚点）"));
    personas.forEach((p) => {
      const s = styleOf(p.name);
      const d = el("div", "drift");
      d.append(el("div", "from", `${s.emoji} ${p.name}`), el("div", "", p.stance));
      wrap.appendChild(d);
    });
  }

  function appendMessage(speaker, content, opts = {}) {
    const s = styleOf(speaker);
    const msg = el("div", "msg" + (opts.opening ? " opening" : ""));
    const avatar = el("div", "avatar", s.emoji);
    avatar.style.background = s.color;
    const bubble = el("div", "bubble");
    bubble.appendChild(el("div", "who", speaker));
    const txt = el("div", "txt");
    if (opts.opening) {
      txt.append(
        el("div", "tag", "开场陈述轮 · 立场锚点"),
        el("div", "stance", `🗣 立场基线：${stanceOf(speaker)}`),
      );
    }
    txt.appendChild(el("p", "", content));
    bubble.appendChild(txt);
    msg.append(avatar, bubble);
    $("#timeline").appendChild(msg);
    scrollToBottom();
    return msg;
  }

  function getStreaming(speaker) {
    let msg = document.getElementById("stream-msg");
    if (msg && msg.dataset.speaker === speaker) return msg;
    if (msg) msg.remove();
    const s = styleOf(speaker);
    msg = el("div", "msg streaming");
    msg.id = "stream-msg";
    msg.dataset.speaker = speaker;
    const avatar = el("div", "avatar", s.emoji);
    avatar.style.background = s.color;
    const bubble = el("div", "bubble");
    bubble.appendChild(el("div", "who", `${speaker} · 发言中`));
    const txt = el("div", "txt");
    txt.appendChild(el("span", "stream-text"));
    txt.appendChild(el("span", "cursor"));
    bubble.appendChild(txt);
    msg.append(avatar, bubble);
    $("#timeline").appendChild(msg);
    scrollToBottom();
    return msg;
  }

  /* ---------- SSE ---------- */

  function openStream() {
    if (state.es) state.es.close();
    $("#stopBtn").disabled = false;
    hideContinue();
    const es = new EventSource(`/api/discussions/${state.discussionId}/stream`);
    state.es = es;
    es.addEventListener("opening", (e) => onOpening(parseEvent(e)));
    es.addEventListener("token", (e) => onToken(parseEvent(e)));
    es.addEventListener("message", (e) => onMessage(parseEvent(e)));
    es.addEventListener("paused", (e) => onPaused(parseEvent(e)));
    es.addEventListener("terminated", (e) => onTerminated(parseEvent(e)));
    es.addEventListener("error", onStreamError);
  }

  function parseEvent(e) {
    try { return JSON.parse(e.data); } catch (_) { return {}; }
  }

  function onOpening(ev) {
    if (!ev.speaker) return;
    appendMessage(ev.speaker, ev.content, { opening: true });
  }

  function onToken(ev) {
    if (!ev.speaker) return;
    const span = getStreaming(ev.speaker).querySelector(".stream-text");
    span.textContent += ev.content; // 末条打字机流式
    scrollToBottom();
  }

  function onMessage(ev) {
    if (!ev.speaker) return;
    const sp = document.getElementById("stream-msg");
    if (sp) sp.remove();
    appendMessage(ev.speaker, ev.content, {});
    state.turns++;
    updateRounds();
  }

  function onPaused(ev) {
    if (state.es) { state.es.close(); state.es = null; }
    // 暂停态仍可叫停（终止 + 全场总结），故不禁用叫停按钮
    if (ev.summary) {
      const box = $("#summaryBox");
      box.innerHTML = "";
      box.appendChild(el("h4", "", "本轮摘要 · 已达轮次上限（暂停）"));
      box.appendChild(renderMarkdown(ev.summary));
    }
    $("#roundsInfo").textContent = `已暂停 · 达到轮次上限（已讨论 ${state.turns} 条）`;
    showContinue(`已达轮次上限，本次讨论已暂停。`);
  }

  function onTerminated(ev) {
    if (state.es) { state.es.close(); state.es = null; }
    $("#stopBtn").disabled = true;
    hideContinue();
    if (ev.summary) showSummary(ev.summary);
  }

  function onStreamError(e) {
    if (e.data) {
      // 服务端 SSE error 事件（带 data）
      const ev = parseEvent(e);
      if (state.es) { state.es.close(); state.es = null; }
      $("#stopBtn").disabled = false;
      showToast(ev.detail || "讨论发生错误");
    } else {
      // 连接层错误：EventSource 会自动重连
      showToast("连接中断，正在重连…");
    }
  }

  /* ---------- 暂停 / 继续 / 叫停 ---------- */

  function showContinue(hint) {
    $("#continueHint").textContent = hint;
    $("#continueBar").hidden = false;
  }
  function hideContinue() {
    $("#continueBar").hidden = true;
  }

  async function continueDiscussion() {
    const btn = $("#continueBtn");
    btn.disabled = true;
    try {
      const r = await fetch(`/api/discussions/${state.discussionId}/continue`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "继续讨论失败");
      }
      btn.disabled = false;
      openStream(); // 重新消费 SSE
    } catch (e) {
      btn.disabled = false;
      showToast(e.message);
    }
  }

  async function stopDiscussion() {
    const btn = $("#stopBtn");
    btn.disabled = true;
    try {
      const r = await fetch(`/api/discussions/${state.discussionId}/stop`, { method: "POST" });
      if (!r.ok) throw new Error("叫停失败");
      const data = await r.json();
      if (data.status === "terminated") {
        if (state.es) { state.es.close(); state.es = null; }
        hideContinue();
        // 全场总结（mode=final）经 GET detail 拉取后展示 overlay
        const detail = await (await fetch(`/api/discussions/${state.discussionId}`)).json();
        const final = (detail.summaries || []).filter((s) => s.mode === "final").pop();
        showSummary(final ? final.content : "（暂无总结内容）");
      }
    } catch (e) {
      btn.disabled = false;
      showToast(e.message);
    }
  }

  function goSetup() {
    if (state.es) { state.es.close(); state.es = null; }
    hideContinue();
    $("#stopBtn").disabled = false;
    switchView("setup");
  }

  /* ---------- Markdown 迷你渲染（摘要/总结） ---------- */

  function renderMarkdown(text) {
    const root = el("div", "md");
    if (!text) return root;
    const lines = text.split("\n");
    let i = 0;
    while (i < lines.length) {
      const line = lines[i].trim();
      if (!line) { i++; continue; }
      if (/^\|.*\|\s*$/.test(line)) {
        const rows = [];
        while (i < lines.length && /^\|.*\|\s*$/.test(lines[i].trim())) {
          rows.push(lines[i].trim());
          i++;
        }
        root.appendChild(renderTable(rows));
        continue;
      }
      if (/^#{1,6}\s/.test(line)) {
        root.appendChild(el("h4", "", line.replace(/^#{1,6}\s+/, "")));
        i++;
        continue;
      }
      if (/^[-*]\s/.test(line)) {
        root.appendChild(el("p", "li", line.replace(/^[-*]\s+/, "· ")));
        i++;
        continue;
      }
      root.appendChild(el("p", "", line));
      i++;
    }
    return root;
  }

  function renderTable(rows) {
    const table = el("table");
    const split = (row) => row.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    const thead = el("thead");
    const hr = el("tr");
    split(rows[0]).forEach((h) => hr.appendChild(el("th", "", h)));
    thead.appendChild(hr);
    table.appendChild(thead);
    const tbody = el("tbody");
    rows.slice(1).filter((r) => !/^[\s:\-|]+$/.test(r)).forEach((r) => {
      const tr = el("tr");
      split(r).forEach((c) => tr.appendChild(el("td", "", c)));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function showSummary(markdown) {
    const box = $("#summaryContent");
    box.innerHTML = "";
    box.appendChild(el("h3", "", `全场总结 · ${state.topic}`));
    box.appendChild(renderMarkdown(markdown));
    const closeRow = el("div", "close-row");
    const closeBtn = el("button", "close-btn", "关闭");
    closeBtn.addEventListener("click", () => $("#summaryOverlay").classList.remove("show"));
    closeRow.appendChild(closeBtn);
    box.appendChild(closeRow);
    $("#summaryOverlay").classList.add("show");
  }

  /* ---------- 绑定与初始化 ---------- */

  function bind() {
    $("#goBtn").addEventListener("click", startDiscussion);
    $("#manualStop").addEventListener("change", () => {
      $("#maxTurns").disabled = $("#manualStop").checked;
    });
    $("#backBtn").addEventListener("click", goSetup);
    $("#stopBtn").addEventListener("click", stopDiscussion);
    $("#continueBtn").addEventListener("click", continueDiscussion);
    $("#summaryOverlay").addEventListener("click", (e) => {
      if (e.target.id === "summaryOverlay") e.target.classList.remove("show");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bind();
    switchView("setup");
    loadPersonas();
  });
})();
