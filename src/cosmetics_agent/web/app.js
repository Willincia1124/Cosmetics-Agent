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
const template = document.getElementById("message-template");

chatForm.addEventListener("submit", onSubmit);
refreshSessionBtn.addEventListener("click", () => loadSession());
resetSessionBtn.addEventListener("click", () => resetSession());

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
    addWelcomeMessage("会话已重置，现在可以重新开始。");
    await loadSession();
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

  const sections = [];
  sections.push(`<p>${escapeHtml(payload.summary || "已生成推荐。")}</p>`);

  if (payload.profile) {
    sections.push(renderProfile(payload.profile));
  }
  if (payload.recommendations?.length) {
    sections.push(renderRecommendations(payload.recommendations));
  }
  if (payload.clarifying_questions?.length) {
    sections.push(renderListBlock("建议补充的信息", payload.clarifying_questions));
  }
  if (payload.global_cautions?.length) {
    sections.push(renderListBlock("使用提醒", payload.global_cautions));
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

  body.innerHTML = sections.join("");
  chatThread.appendChild(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
}

function appendSystemNotice(text) {
  const article = createMessageCard("assistant");
  article.querySelector(".message-body").innerHTML = `<p>${escapeHtml(text)}</p>`;
  chatThread.appendChild(article);
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
  const cards = recommendations
    .map((item, index) => {
      const product = item.product || {};
      const evidence = item.evidence?.map((chunk) => chunk.title).join("、");
      const links = item.purchase_links?.map((link) => `<li><a href="${escapeAttribute(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.platform || "购买链接")}</a></li>`).join("") || "";
      return `
        <article class="recommendation-card">
          <h4>${index + 1}. ${escapeHtml(product.name || "未命名商品")}</h4>
          <div class="kv">
            <span class="tag">${escapeHtml(product.brand || "Unknown")}</span>
            <span class="tag">${escapeHtml(product.category || "Unknown")}</span>
            <span class="tag">${escapeHtml(String(product.price ?? "-"))} 元</span>
          </div>
          <div class="inline-list">
            <ul>
              ${(item.reasons || []).slice(0, 3).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
            </ul>
          </div>
          ${product.notes ? `<p class="muted">${escapeHtml(product.notes)}</p>` : ""}
          ${evidence ? `<p class="muted">知识依据：${escapeHtml(evidence)}</p>` : ""}
          ${item.live_insights?.length ? `<p class="muted">实时线索：${escapeHtml(item.live_insights.join("；"))}</p>` : ""}
          ${links ? `<div class="links"><strong>购买链接</strong><ul>${links}</ul></div>` : ""}
        </article>
      `;
    })
    .join("");

  return `
    <section class="section-block">
      <h3>推荐结果</h3>
      <div class="recommendation-grid">${cards}</div>
    </section>
  `;
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
