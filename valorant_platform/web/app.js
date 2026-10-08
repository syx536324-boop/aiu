// Owns frontend routing, agent search, chat state, and Dify stream rendering.
const root = document.querySelector("#view-root");
const crumb = document.querySelector("#crumb-current");
const PUBLIC_STATIC_PREVIEW = location.hostname.endsWith(".github.io");
const roleColors = { "决斗": "#ff6471", "先锋": "#c58cff", "控场": "#64d9ff", "哨卫": "#8bdc83" };
const roleKeys = { "决斗": "duel", "先锋": "initiator", "控场": "controller", "哨卫": "sentinel" };
const maps = [
  { slug: "bind", name: "源工重镇", english: "BIND" },
  { slug: "haven", name: "隐士修所", english: "HAVEN" },
  { slug: "split", name: "霓虹町", english: "SPLIT" },
  { slug: "ascent", name: "亚海悬城", english: "ASCENT" },
  { slug: "icebox", name: "森寒冬港", english: "ICEBOX" },
  { slug: "breeze", name: "微风岛屿", english: "BREEZE" },
  { slug: "fracture", name: "裂变峡谷", english: "FRACTURE" },
  { slug: "pearl", name: "深海明珠", english: "PEARL" },
  { slug: "lotus", name: "莲花古城", english: "LOTUS" },
  { slug: "sunset", name: "日落之城", english: "SUNSET" },
  { slug: "abyss", name: "幽邃地窟", english: "ABYSS" },
  { slug: "corrode", name: "盐海矿镇", english: "CORRODE" },
  { slug: "summit", name: "天枢云阙", english: "SUMMIT" }
];
let agents = [];
let fadeLineups = [];
let libraryRole = "全部";
let librarySearch = "";
let toastTimer;
const storedUser = localStorage.getItem("aiu.valorant.user") || crypto.randomUUID();
localStorage.setItem("aiu.valorant.user", storedUser);
let conversationId = localStorage.getItem("aiu.valorant.conversation") || "";
let messages = [{ type: "assistant", text: PUBLIC_STATIC_PREVIEW
  ? "当前为公开静态预览版：可以浏览特工资料与地图页面。智能问答依赖本机 Dify/Ollama，暂未对外开放。"
  : "上号。地图、枪法、阵容，或者想练哪位特工？直接问我。\n\n输入一个特工名会打开他的资料页；也可以从右侧快速选人。" }];

if (PUBLIC_STATIC_PREVIEW) {
  const connectionCard = document.querySelector(".connection-card");
  connectionCard.classList.add("preview-mode");
  connectionCard.querySelector("strong").textContent = "公开静态预览";
  connectionCard.querySelector("small").textContent = "CHAT SERVICE NOT DEPLOYED";
  document.querySelector(".build-tag").textContent = "PUBLIC PREVIEW";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function agentSlug(agent) {
  return agent.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function normalize(value) {
  return String(value).toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

function findExactAgent(value) {
  const target = normalize(value);
  if (!target) return null;
  return agents.find((agent) => [agent.name, agent.cn, ...(agent.aliases || [])].some((alias) => normalize(alias) === target)) || null;
}

function findAgentBySlug(slug) {
  return agents.find((agent) => agentSlug(agent) === slug) || null;
}

function showToast(text, isError = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = text;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function roleDotClass(role) {
  return roleKeys[role] || "duel";
}

function renderLineupCard(entry) {
  const chapters = entry.chapters.map((chapter) => {
    const media = chapter.mediaUrl ? `<a class="lineup-media-link" href="${escapeHtml(chapter.mediaUrl)}" target="_blank" rel="noreferrer">查看演示</a>` : `<span class="lineup-media-pending">动图待截取</span>`;
    const preview = chapter.mediaUrl ? `<img class="lineup-preview" src="${escapeHtml(chapter.mediaUrl)}" alt="${escapeHtml(entry.mapName)} ${escapeHtml(chapter.title)} 技能点位演示" loading="lazy" />` : "";
    return `<div class="lineup-chapter"><time>${escapeHtml(chapter.time)}</time><span>${escapeHtml(chapter.title)}</span>${media}</div>${preview}`;
  }).join("");
  return `<article class="lineup-entry"><div class="lineup-entry-head"><div><span class="lineup-id">${escapeHtml(entry.sourceLabel || "黑梦点位条目")}</span><h3>${escapeHtml(entry.mapName)}</h3></div><span class="lineup-status">${escapeHtml(entry.status)}</span></div>${entry.note ? `<p class="lineup-note">${escapeHtml(entry.note)}</p>` : ""}${entry.chapters.length ? `<div class="lineup-chapters"><div class="lineup-chapters-title">视频章节 · ${entry.chapters.length} 个章节</div>${chapters}</div>` : `<div class="lineup-pending"><span>尚未读取视频章节</span><small>保留原始来源，读取后再补充点位说明与演示动图。</small></div>`}<a class="lineup-source" href="${escapeHtml(entry.sourceUrl)}" target="_blank" rel="noreferrer">打开视频来源 ↗</a></article>`;
}

function renderMessages() {
  const log = document.querySelector("#chat-log");
  if (!log) return;
  log.innerHTML = messages.map((message) => `
    <article class="message ${message.type === "user" ? "user" : "assistant"}">
      <div class="message-badge">${message.type === "user" ? "YOU" : "AIU"}</div>
      <div class="message-copy"><div class="message-meta">${message.type === "user" ? "OPERATOR" : "VALORANT FIELD EXPERT"}</div>
        <div class="message-text ${message.pending ? "pending" : ""} ${message.error ? "error" : ""}">${escapeHtml(message.text)}</div>
      </div>
    </article>`).join("");
  log.scrollTop = log.scrollHeight;
}

function renderHome() {
  crumb.textContent = "作战终端";
  root.innerHTML = `
    <section class="home-view">
      <div class="home-head">
        <div><div class="eyebrow">ROUND START // FIELD SUPPORT</div>
          <h1 class="home-title">枪要打准，<em>话也要报准。</em></h1>
          <p class="home-subtitle">${PUBLIC_STATIC_PREVIEW ? "VALORANT 特工与技能资料公开预览。" : "你的本地 VALORANT 战术搭子。聊打法、问特工；输入特工名，直接打开资料页。"}</p>
        </div>
        <div class="home-stat"><strong class="stat-number">29</strong><div class="stat-caption">位现役特工<small>ROSTER INDEX / 2026</small></div></div>
      </div>
      <div class="home-grid">
        <section class="panel chat-panel">
          <div class="panel-heading">
            <div class="panel-heading-title"><span class="bot-icon">⌁</span><div><strong>战术询问窗口</strong><small>${PUBLIC_STATIC_PREVIEW ? "PUBLIC PREVIEW · CHAT OFFLINE" : "AIU FIELD EXPERT · LOCAL QWEN"}</small></div></div>
            <span class="pill-live">${PUBLIC_STATIC_PREVIEW ? "● PREVIEW" : "● LIVE"}</span>
          </div>
          <div id="chat-log" class="chat-log" aria-live="polite"></div>
          <div class="starter-prompts" ${PUBLIC_STATIC_PREVIEW ? "hidden" : ""}><button data-prompt="捷风">打开捷风资料</button><button data-prompt="这回合该怎么打？">这回合怎么打？</button><button data-prompt="新手先练哪个位置？">新手怎么练？</button></div>
          <div class="composer-wrap"><form id="chat-form" class="composer">
            <textarea id="prompt-input" rows="1" maxlength="4000" placeholder="${PUBLIC_STATIC_PREVIEW ? "公开预览版暂未接入在线问答" : "输入问题或特工名称…"}" aria-label="输入问题或特工名称" ${PUBLIC_STATIC_PREVIEW ? "disabled" : ""}></textarea>
            <button class="send-button" type="submit" aria-label="发送问题" ${PUBLIC_STATIC_PREVIEW ? "disabled" : ""}><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h13M12 5l7 7-7 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
          </form><div class="input-hint">${PUBLIC_STATIC_PREVIEW ? "公开预览可浏览特工资料与地图目录；在线问答暂未开放。" : "<span>ENTER 发送 <b>·</b> SHIFT + ENTER 换行</span><span>输入角色名打开资料页 ↗</span>"}</div></div>
        </section>
        <aside class="panel intel-panel">
          <div class="panel-heading"><div class="panel-heading-title"><span class="bot-icon">▦</span><div><strong>特工速查</strong><small>AGENT SELECT / QUICK PICK</small></div></div><span class="pill-live">29 AGENTS</span></div>
          <div class="intel-caption">本周练习推荐 / PICKS</div>
          <div id="agent-spotlight" class="agent-spotlight"></div>
          <div class="intel-caption">战术定位 / ROLES</div>
          <div class="role-guide">
            <div class="role-guide-row"><i class="role-dot duel"></i>决斗手<span>DUELIST</span></div>
            <div class="role-guide-row"><i class="role-dot initiator"></i>先锋<span>INITIATOR</span></div>
            <div class="role-guide-row"><i class="role-dot controller"></i>控场<span>CONTROLLER</span></div>
            <div class="role-guide-row"><i class="role-dot sentinel"></i>哨卫<span>SENTINEL</span></div>
          </div>
          <button class="library-cta" data-view="library"><span><strong>打开完整特工资料库</strong><small>浏览全部角色 · 按定位筛选</small></span><span class="cta-arrow">↗</span></button>
        </aside>
      </div>
      <div class="home-footer-note"><span>${PUBLIC_STATIC_PREVIEW ? "AIU // PUBLIC VALORANT PREVIEW" : "PERSONA // 沉迷无畏契约的高分段老玩家"}</span><span>特工技能摘要已整理 · 技能点位持续留白</span></div>
    </section>`;
  const picks = ["Jett", "Omen", "Sova", "Killjoy"].map((name) => agents.find((agent) => agent.name === name)).filter(Boolean);
  document.querySelector("#agent-spotlight").innerHTML = picks.map((agent) => `
    <button class="spotlight-card" data-agent-slug="${agentSlug(agent)}" style="--accent:${roleColors[agent.role]}">
      <span class="agent-role">${escapeHtml(agent.role)} // ${roleKeys[agent.role].toUpperCase()}</span><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.cn)}</small>
    </button>`).join("");
  renderMessages();
  document.querySelector("#chat-form").addEventListener("submit", onChatSubmit);
  document.querySelector("#prompt-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit(); }
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
    const exact = findExactAgent(button.dataset.prompt);
    if (exact) { navigate(`#/agents/${agentSlug(exact)}`); return; }
    const input = document.querySelector("#prompt-input");
    input.value = button.dataset.prompt;
    input.focus();
    input.form.requestSubmit();
  }));
}

function drawAgentGrid(grid, source) {
  const filtered = source.filter((agent) => {
    const matchesRole = libraryRole === "全部" || agent.role === libraryRole;
    const haystack = normalize([agent.name, agent.cn, ...(agent.aliases || [])].join(" "));
    return matchesRole && (!librarySearch || haystack.includes(normalize(librarySearch)));
  });
  document.querySelector("#result-count").textContent = `${String(filtered.length).padStart(2, "0")} AGENTS FOUND`;
  grid.innerHTML = filtered.length ? filtered.map((agent, index) => `
    <button class="agent-card" data-agent-slug="${agentSlug(agent)}" style="--accent:${roleColors[agent.role]}">
      <span class="card-top"><span class="agent-index">${String(index + 1).padStart(2, "0")} / ${String(filtered.length).padStart(2, "0")}</span><span class="card-role">${escapeHtml(agent.role)} · ${roleKeys[agent.role].toUpperCase()}</span></span>
      <h3>${escapeHtml(agent.name)}</h3><p class="agent-chinese">${escapeHtml(agent.cn)}</p>
      <span class="card-bottom"><span class="agent-index">VIEW FIELD DOSSIER</span><span class="card-arrow">↗</span></span>
    </button>`).join("") : `<div class="empty-results">没有找到这位特工。试试中文名或英文名。</div>`;
}

function renderLibrary() {
  crumb.textContent = "特工资料库";
  root.innerHTML = `
    <section class="library-view">
      <div class="section-head"><div><div class="eyebrow">PERSONNEL DATABASE // ACCESS GRANTED</div><h1 class="section-title">特工资料库<span style="color:var(--red)">.</span></h1><p class="section-copy">点选一位特工查看技能摘要；进入技能点位页可按地图查看，实战站位与投掷方法后续补充。</p></div><div class="section-counter">29<span> / AGENTS</span></div></div>
      <div class="filterbar"><div class="filter-tabs" role="group" aria-label="按定位筛选">${["全部", "决斗", "先锋", "控场", "哨卫"].map((role) => `<button class="filter-chip ${libraryRole === role ? "active" : ""}" data-library-role="${role}">${role}</button>`).join("")}</div>
        <label class="search-box"><span>⌕</span><input id="agent-search" type="search" placeholder="搜索中文名 / 英文名" value="${escapeHtml(librarySearch)}" autocomplete="off" /></label></div>
      <div id="result-count" class="result-count"></div><div id="agent-grid" class="agent-grid"></div>
    </section>`;
  const grid = document.querySelector("#agent-grid");
  drawAgentGrid(grid, agents);
  document.querySelector("#agent-search").addEventListener("input", (event) => {
    librarySearch = event.currentTarget.value;
    drawAgentGrid(grid, agents);
  });
  document.querySelectorAll("[data-library-role]").forEach((button) => button.addEventListener("click", () => {
    libraryRole = button.dataset.libraryRole;
    renderLibrary();
  }));
}

function renderAgent(agent, tabName, mapSlug = "") {
  crumb.textContent = agent.name.toUpperCase();
  const isPoints = tabName === "points";
  const selectedMap = isPoints ? maps.find((map) => map.slug === mapSlug) : null;
  const skillCards = (agent.skills || []).map((skill, index) => `
    <article class="skill-card">
      <div class="skill-card-top"><span class="skill-index">${String(index + 1).padStart(2, "0")}</span>${skill.key
        ? `<span class="skill-hotkey"><kbd>${escapeHtml(skill.key)}</kbd> 默认键</span>`
        : `<span class="skill-hotkey passive">被动机制</span>`}</div>
      <h2>${escapeHtml(skill.name)}</h2>
      <p>${escapeHtml(skill.description)}</p>
    </article>`).join("");
  const selectedLineups = selectedMap && agent.name === "Fade" ? fadeLineups.filter((entry) => entry.mapSlug === selectedMap.slug) : [];
  const lineupCards = selectedLineups.map(renderLineupCard).join("");
  root.innerHTML = `
    <section class="agent-view">
      <a class="back-link" href="#/library"><span>←</span> 返回特工资料库</a>
      <div class="agent-hero" style="--accent:${roleColors[agent.role]}">
        <div class="agent-portrait-wrap"><img class="agent-portrait" src="${escapeHtml(agent.portrait_url)}" alt="${escapeHtml(agent.name)}《VALORANT》特工立绘" decoding="async" /></div>
        <div class="agent-hero-content"><div class="eyebrow">AGENT FILE // ${escapeHtml(agentSlug(agent).toUpperCase())}</div><h1 class="agent-name">${escapeHtml(agent.name)}</h1><p class="agent-name-cn">${escapeHtml(agent.cn)}</p><span class="agent-role-tag"><i class="role-dot ${roleDotClass(agent.role)}"></i>${escapeHtml(agent.role)} / ${roleKeys[agent.role].toUpperCase()}</span></div>
        <div class="agent-counter">${String(agents.indexOf(agent) + 1).padStart(2, "0")}</div>
      </div>
      <div class="detail-toolbar"><nav class="detail-tabs" aria-label="特工资料导航">
        <a class="detail-tab ${!isPoints ? "active" : ""}" href="#/agents/${agentSlug(agent)}?tab=skills">技能介绍</a>
        <a class="detail-tab ${isPoints ? "active" : ""}" href="#/agents/${agentSlug(agent)}?tab=points">技能点位</a>
      </nav><small>${isPoints ? "LINEUP NOTES · 待补充" : "DEFAULT PC KEYBINDS · 游戏设置可自定义"}</small></div>
      ${isPoints
        ? selectedMap
          ? `<div class="map-page-heading"><a href="#/agents/${agentSlug(agent)}?tab=points">← 返回地图列表</a><div><span>${selectedMap.english} // SKILL LINEUPS</span><h2>${selectedMap.name}</h2></div></div><div class="detail-content lineup-content">${lineupCards || `<div class="blank-state"><i class="blank-mark" aria-hidden="true"></i><strong>LINEUP DATABASE / EMPTY</strong><span>${selectedMap.name} 暂无已登记条目</span></div>`}</div>`
          : `<section class="map-picker"><div class="map-picker-heading"><div><div class="eyebrow">MAP INDEX // 13 TACTICAL MAPS</div><h2>选择地图</h2><p>选择一张地图，进入对应的技能点位页面。</p></div><span>13 MAPS</span></div><div class="map-grid">${maps.map((map, index) => `
            <a class="map-card" href="#/agents/${agentSlug(agent)}?tab=points&map=${map.slug}">
              <span class="map-card-index">${String(index + 1).padStart(2, "0")} / MAP</span><strong>${map.name}</strong><span class="map-card-bottom"><span>${map.english}</span><span class="card-arrow">↗</span></span>
            </a>`).join("")}</div></section>`
        : `<div class="detail-content skills-content"><div class="skill-list">${skillCards}</div></div>`}
      <div class="detail-footer"><span>AGENT INDEX / ${String(agents.indexOf(agent) + 1).padStart(2, "0")} OF ${agents.length}</span><a href="${escapeHtml(agent.official_url)}" target="_blank" rel="noreferrer">查看 Riot 官方资料 ↗</a></div>
    </section>`;
}

function navigate(hash) {
  if (location.hash === hash) renderRoute();
  else location.hash = hash;
}

function renderRoute() {
  const hash = location.hash || "#/";
  const agentMatch = hash.match(/^#\/agents\/([^?]+)/);
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.toggle("active", (agentMatch ? "library" : hash.includes("library") ? "library" : "home") === link.dataset.view));
  if (agentMatch) {
    const agent = findAgentBySlug(decodeURIComponent(agentMatch[1]));
    if (!agent) { navigate("#/library"); return; }
    const params = new URLSearchParams(hash.split("?")[1] || "");
    renderAgent(agent, params.get("tab") || "skills", params.get("map") || "");
  } else if (hash.startsWith("#/library")) renderLibrary();
  else renderHome();
  window.scrollTo({ top: 0, behavior: "instant" });
}

async function onChatSubmit(event) {
  event.preventDefault();
  if (PUBLIC_STATIC_PREVIEW) return;
  const input = document.querySelector("#prompt-input");
  const query = input.value.trim();
  if (!query || event.currentTarget.dataset.busy === "true") return;
  const exactAgent = findExactAgent(query);
  if (exactAgent) { navigate(`#/agents/${agentSlug(exactAgent)}`); return; }

  input.value = "";
  messages.push({ type: "user", text: query });
  messages.push({ type: "assistant", text: "正在读局…", pending: true });
  renderMessages();
  const form = event.currentTarget;
  const sendButton = form.querySelector(".send-button");
  form.dataset.busy = "true";
  sendButton.disabled = true;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, user: storedUser, conversation_id: conversationId })
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      throw new Error(problem.error || `服务响应异常（${response.status}）`);
    }
    await readDifyStream(response);
  } catch (error) {
    const last = messages[messages.length - 1];
    last.text = error.message || "连接失败，请确认 Dify 智能体已启动。";
    last.pending = false;
    last.error = true;
    renderMessages();
  } finally {
    form.dataset.busy = "false";
    sendButton.disabled = false;
    input.focus();
  }
}

async function readDifyStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  const placeholder = messages[messages.length - 1];

  function consumeFrame(frame) {
    const dataLines = frame.split(/\r?\n/).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim());
    if (!dataLines.length) return;
    const dataText = dataLines.join("\n");
    if (dataText === "[DONE]") return;
    let data;
    try { data = JSON.parse(dataText); } catch { return; }
    if (data.conversation_id) {
      conversationId = data.conversation_id;
      localStorage.setItem("aiu.valorant.conversation", conversationId);
    }
    if (data.event === "error") throw new Error(data.message || data.code || "Dify 生成回复时发生错误。");
    if (["message", "agent_message"].includes(data.event) && typeof data.answer === "string") {
      answer += data.answer;
      placeholder.text = answer;
      renderMessages();
    }
    if (data.event === "message_end" && data.conversation_id) {
      conversationId = data.conversation_id;
      localStorage.setItem("aiu.valorant.conversation", conversationId);
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";
      for (const frame of frames) consumeFrame(frame);
      if (done) break;
    }
    if (buffer.trim()) consumeFrame(buffer);
  } catch (error) {
    placeholder.text = answer ? `${answer}\n\n[连接中断：${error.message}]` : error.message;
    placeholder.pending = false;
    placeholder.error = !answer;
    renderMessages();
    return;
  }
  placeholder.text = answer || "这次没有收到可显示的回复，再问我一次试试。";
  placeholder.pending = false;
  renderMessages();
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.view === "library") { libraryRole = "全部"; librarySearch = ""; navigate("#/library"); }
  else navigate("#/");
}));
document.querySelectorAll("[data-role-filter]").forEach((button) => button.addEventListener("click", () => {
  libraryRole = button.dataset.roleFilter;
  librarySearch = "";
  navigate("#/library");
}));
root.addEventListener("click", (event) => {
  const libraryLink = event.target.closest('[data-view="library"]');
  if (libraryLink) { libraryRole = "全部"; librarySearch = ""; navigate("#/library"); return; }
  const card = event.target.closest("[data-agent-slug]");
  if (card) navigate(`#/agents/${card.dataset.agentSlug}`);
});
document.querySelector("#new-chat").addEventListener("click", () => {
  conversationId = "";
  messages = [{ type: "assistant", text: PUBLIC_STATIC_PREVIEW
    ? "当前为公开静态预览版：可以浏览特工资料与地图页面。智能问答依赖本机 Dify/Ollama，暂未对外开放。"
    : "新的一局，准备好了。报个地图和位置，我陪你把回合拆开。" }];
  localStorage.removeItem("aiu.valorant.conversation");
  if (location.hash && !location.hash.startsWith("#/agents/")) renderRoute();
  else if (!location.hash || location.hash === "#/" || location.hash.startsWith("#/agents/")) navigate("#/");
  showToast("新对话已开启，上一局的聊天上下文已清空。");
});
window.addEventListener("hashchange", renderRoute);

fetch("./agents.json").then((response) => {
  if (!response.ok) throw new Error("角色目录加载失败");
  return response.json();
}).then((data) => {
  agents = data;
  renderRoute();
}).catch(() => {
  root.innerHTML = `<div class="empty-results">特工目录暂时无法加载，请刷新页面。</div>`;
});

fetch(PUBLIC_STATIC_PREVIEW ? "./fade_lineups.json" : "/api/fade-lineups").then((response) => {
  if (!response.ok && !PUBLIC_STATIC_PREVIEW) return fetch("./fade_lineups.json");
  if (!response.ok) throw new Error("黑梦点位目录加载失败");
  return response.json();
}).then((data) => {
  fadeLineups = Array.isArray(data.lineups) ? data.lineups : [];
  if (agents.length) renderRoute();
}).catch(() => {
  fadeLineups = [];
});
