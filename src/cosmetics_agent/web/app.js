const chatThread = document.getElementById("chat-thread");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const statusText = document.getElementById("status-text");
const sendBtn = document.getElementById("send-btn");
const sessionIdInput = document.getElementById("session-id");
const userIdInput = document.getElementById("user-id");
const topKInput = document.getElementById("top-k");
const refreshSessionBtn = document.getElementById("refresh-session");
const resetSessionBtn = document.getElementById("reset-session");
const sessionSummary = document.getElementById("session-summary");
const longTermMemories = document.getElementById("long-term-memories");
const historyList = document.getElementById("history-list");
const openControlsBtn = document.getElementById("open-controls");
const closeControlsBtn = document.getElementById("close-controls");
const toggleDevModeBtn = document.getElementById("toggle-dev-mode");
const controlDrawer = document.getElementById("control-drawer");
const panelBackdrop = document.getElementById("panel-backdrop");
const template = document.getElementById("message-template");
let devMode = false;
const assistantMessages = [];

chatForm.addEventListener("submit", onSubmit);
refreshSessionBtn.addEventListener("click", () => loadSession());
resetSessionBtn.addEventListener("click", () => resetSession());
openControlsBtn.addEventListener("click", () => toggleControls(true));
closeControlsBtn.addEventListener("click", () => toggleControls(false));
toggleDevModeBtn.addEventListener("click", () => toggleDevMode());
panelBackdrop.addEventListener("click", () => toggleControls(false));

addWelcomeMessage();
loadSession();

async function onSubmit(event) {
  event.preventDefault();
  const query = chatInput.value.trim();
  if (!query) return;

  appendUserMessage(query);
  chatInput.value = "";
  setLoading(true, "正在分析你的需求...");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        session_id: sessionIdInput.value.trim(),
        user_id: userIdInput.value.trim(),
        top_k: Number(topKInput.value) || 3,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "请求失败");
    }
    appendAssistantMessage(data);
    await loadSession();
    setLoading(false, "准备就绪");
  } catch (error) {
    appendSystemNotice(`请求失败：${error.message}`);
    setLoading(false, "请求失败");
  }
}

async function loadSession() {
  try {
    const params = new URLSearchParams({
      user_id: userIdInput.value.trim(),
      message_window: "6",
    });
    const response = await fetch(`/api/session/${encodeURIComponent(sessionIdInput.value.trim())}?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "加载会话失败");
    }
    sessionSummary.textContent = data.session_summary || "暂无会话摘要";
    renderHistory(data.recent_messages || []);
    longTermMemories.innerHTML = "";
    const memories = data.long_term_memories || [];
    if (!memories.length) {
      const empty = document.createElement("span");
      empty.className = "chip";
      empty.textContent = "暂无长期记忆";
      longTermMemories.appendChild(empty);
      return;
    }
    memories.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = item.content;
      longTermMemories.appendChild(chip);
    });
  } catch (error) {
    sessionSummary.textContent = `加载会话失败：${error.message}`;
  }
}

async function resetSession() {
  setLoading(true, "正在清空当前会话...");
  try {
    const response = await fetch(`/api/session/${encodeURIComponent(sessionIdInput.value.trim())}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userIdInput.value.trim(),
        message_window: 6,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "重置失败");
    }
    chatThread.innerHTML = "";
    assistantMessages.length = 0;
    addWelcomeMessage("会话已重置，现在可以重新开始。");
    await loadSession();
    toggleControls(false);
    setLoading(false, "会话已重置");
  } catch (error) {
    appendSystemNotice(`重置失败：${error.message}`);
    setLoading(false, "重置失败");
  }
}

function addWelcomeMessage(text = "你好，我已经准备好帮你做美妆/护肤推荐了。你可以直接描述肤质、预算、场景和想避开的成分。") {
  const article = createMessageCard("assistant");
  article.querySelector(".message-body").innerHTML = `<p>${escapeHtml(text)}</p>`;
  chatThread.appendChild(article);
}

function appendUserMessage(text) {
  const article = createMessageCard("user");
  article.querySelector(".message-body").innerHTML = `<p>${escapeHtml(text)}</p>`;
  chatThread.appendChild(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
}

function appendAssistantMessage(payload) {
  const article = createMessageCard("assistant");
  const body = article.querySelector(".message-body");

  body.innerHTML = renderAssistantSections(payload);
  assistantMessages.push({ body, payload });
  chatThread.appendChild(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
}

function renderAssistantSections(payload) {
  const sections = [];
  sections.push(`<p class="assistant-summary">${escapeHtml(payload.summary || "已生成推荐。")}</p>`);
  if (payload.recommendations?.length) {
    sections.push(renderRecommendations(payload.recommendations));
  }
  if (payload.clarifying_questions?.length) {
    sections.push(renderListBlock("建议补充的信息", payload.clarifying_questions));
  }
  if (payload.global_cautions?.length) {
    sections.push(renderListBlock("使用提醒", payload.global_cautions));
  }

  if (devMode) {
    if (payload.profile) {
      sections.push(renderProfile(payload.profile));
    }
    if (payload.plan_steps?.length) {
      sections.push(renderListBlock("Planner 执行计划", payload.plan_steps));
    }
    if (payload.self_check_notes?.length) {
      sections.push(renderListBlock("Self-check", payload.self_check_notes));
    }
    if (payload.tool_events?.length) {
      sections.push(renderToolEvents(payload.tool_events));
    }
  }

  return sections.join("");
}

function appendSystemNotice(text) {
  const article = createMessageCard("assistant");
  article.querySelector(".message-body").innerHTML = `<p>${escapeHtml(text)}</p>`;
  chatThread.appendChild(article);
}

function renderHistory(messages) {
  historyList.innerHTML = "";
  if (!messages.length) {
    historyList.innerHTML = `<div class="history-empty">还没有历史记录，先开始一轮对话吧。</div>`;
    return;
  }

  messages.forEach((item) => {
    const card = document.createElement("article");
    card.className = `history-card ${item.role}`;
    card.innerHTML = `
      <div class="history-role">${item.role === "user" ? "你" : "助手"}</div>
      <div class="history-text">${escapeHtml(item.content)}</div>
    `;
    historyList.appendChild(card);
  });
}

function toggleControls(open) {
  controlDrawer.classList.toggle("open", open);
  controlDrawer.setAttribute("aria-hidden", String(!open));
  panelBackdrop.hidden = !open;
}

function toggleDevMode() {
  devMode = !devMode;
  toggleDevModeBtn.setAttribute("aria-pressed", String(devMode));
  toggleDevModeBtn.textContent = devMode ? "Develop Mode · ON" : "Develop Mode";
  assistantMessages.forEach((message) => {
    message.body.innerHTML = renderAssistantSections(message.payload);
  });
}

function createMessageCard(role) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".message-role").textContent = role === "user" ? "你" : "Cosmetics Agent";
  return node;
}

function renderProfile(profile) {
  const chips = [];
  if (profile.skin_types?.length) chips.push(...profile.skin_types.map((item) => `肤质: ${item}`));
  if (profile.concerns?.length) chips.push(...profile.concerns.map((item) => `诉求: ${item}`));
  if (profile.desired_categories?.length) chips.push(...profile.desired_categories.map((item) => `品类: ${item}`));
  if (profile.budget_max != null) chips.push(`预算: ${profile.budget_min ?? 0}-${profile.budget_max}`);
  if (profile.avoided_ingredients?.length) chips.push(...profile.avoided_ingredients.map((item) => `避开: ${item}`));
  if (!chips.length) return "";

  return `
    <section class="section-block">
      <h3>结构化画像</h3>
      <div class="kv">${chips.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}</div>
    </section>
  `;
}

function renderRecommendations(recommendations) {
  const topRecommendations = recommendations.slice(0, 3);
  const summary = buildRecommendationSummary(topRecommendations);
  const cards = topRecommendations
    .map((item, index) => {
      const product = item.product || {};
      const evidence = item.evidence?.map((chunk) => chunk.title).join("、");
      const links = item.purchase_links?.map((link) => `<li><a href="${escapeAttribute(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.platform || "购买链接")}</a></li>`).join("") || "";
      const features = buildProductFeatures(product);
      const reasons = (item.reasons || []).slice(0, 3);
      const advantage = reasons.join("；") || "与你的肤质、预算和使用诉求整体匹配。";
      return `
        <article class="recommendation-card featured">
          <div class="recommendation-rank">推荐 ${index + 1}</div>
          <div class="recommendation-main">
            <div>
              <h4>${escapeHtml(product.name || "未命名商品")}</h4>
              <p class="product-subtitle">${escapeHtml(product.brand || "Unknown")} · ${escapeHtml(product.category || "Unknown")} · ${escapeHtml(String(product.price ?? "-"))} 元</p>
            </div>
            ${devMode ? `<div class="score-pill">匹配度 ${escapeHtml(formatScore(item.score))}</div>` : ""}
          </div>

          <p class="recommendation-copy">${escapeHtml(advantage)}</p>
          <div class="feature-pills">
            ${features.map((feature) => `<span>${escapeHtml(feature)}</span>`).join("")}
          </div>

          ${product.notes && devMode ? `<p class="muted">商品备注：${escapeHtml(product.notes)}</p>` : ""}
          ${evidence && devMode ? `<p class="muted">知识依据：${escapeHtml(evidence)}</p>` : ""}
          ${item.live_insights?.length && devMode ? `<p class="muted">实时线索：${escapeHtml(item.live_insights.join("；"))}</p>` : ""}
          ${links ? `<div class="links purchase-links"><strong>购买入口</strong><ul>${links}</ul></div>` : ""}
        </article>
      `;
    })
    .join("");

  return `
    <section class="section-block">
      <h3>推荐方案</h3>
      <div class="recommendation-overview">
        <strong>${escapeHtml(summary.title)}</strong>
        <p>${escapeHtml(summary.description)}</p>
      </div>
      <div class="recommendation-grid">${cards}</div>
    </section>
  `;
}

function buildRecommendationSummary(recommendations) {
  if (!recommendations.length) {
    return {
      title: "暂时没有找到特别匹配的商品",
      description: "可以补充肤质、预算、使用场景或想避开的成分，我会继续缩小范围。",
    };
  }

  const top = recommendations[0];
  const product = top.product || {};
  const names = recommendations.map((item) => item.product?.name).filter(Boolean);
  const concerns = top.reasons?.slice(0, 2).join("；") || "综合匹配度较高";
  return {
    title: `优先推荐 ${product.name || names[0] || "第 1 个商品"}`,
    description: `这次筛出 ${recommendations.length} 个候选，整体优先考虑肤质适配、预算、功效诉求和成分避雷。首推理由是：${concerns}。`,
  };
}

function buildProductFeatures(product) {
  const features = [];
  if (product.finish) features.push(`肤感/妆效偏 ${product.finish}`);
  if (product.tags?.length) features.push(`关键词：${product.tags.slice(0, 3).join("、")}`);
  if (product.hero_ingredients?.length) features.push(`核心成分：${product.hero_ingredients.slice(0, 3).join("、")}`);
  if (product.free_from_ingredients?.length) features.push(`避开：${product.free_from_ingredients.slice(0, 3).join("、")}`);
  if (!features.length) features.push("综合定位均衡，适合作为备选。");
  return features.slice(0, 4);
}

function formatScore(score) {
  if (score == null || Number.isNaN(Number(score))) return "-";
  return Number(score).toFixed(1);
}

function renderListBlock(title, items) {
  return `
    <section class="section-block">
      <h3>${escapeHtml(title)}</h3>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>
  `;
}

function renderToolEvents(events) {
  return `
    <section class="section-block">
      <h3>Tool Calling 记录</h3>
      <div class="recommendation-grid">
        ${events
          .map(
            (event) => `
              <article class="info-card">
                <strong>${escapeHtml(event.tool_name)}</strong>
                <p class="muted">状态：${escapeHtml(event.status)}</p>
                <p class="muted">输入：${escapeHtml(event.input_summary)}</p>
                <p class="muted">输出：${escapeHtml(event.output_summary)}</p>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function setLoading(loading, text) {
  sendBtn.disabled = loading;
  chatInput.disabled = loading;
  statusText.textContent = text;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(text) {
  return escapeHtml(text);
}
