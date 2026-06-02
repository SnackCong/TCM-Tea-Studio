const constitutions = ["平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"];

const state = {
  clients: [],
  formulas: [],
  formulaTemplates: [],
  clientSessions: [],
  clientFormulas: [],
  clientTodos: [],
  selectedClientId: "",
  currentView: "dashboard",
  user: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function uid(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 401) {
    showLogin();
    throw new Error("未登录或会话已过期");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  window.setTimeout(() => el.classList.remove("show"), 1800);
}

function showLogin(message = "") {
  document.body.classList.add("auth-required");
  $("#loginMessage").textContent = message;
  $("#loginPassword").value = "";
}

function showApp() {
  document.body.classList.remove("auth-required");
  $("#currentUser").textContent = state.user?.username || "已登录";
}

async function refreshData() {
  const data = await api("/api/data");
  state.clients = data.clients || [];
  state.formulas = data.formulas || [];
  state.formulaTemplates = data.formulaTemplates || [];
  state.clientSessions = data.clientSessions || [];
  state.clientFormulas = data.clientFormulas || [];
  state.clientTodos = data.clientTodos || [];
  renderAll();
}

function setView(view) {
  state.currentView = view;
  $$(".view").forEach((el) => el.classList.remove("active"));
  $(`#${view}View`).classList.add("active");
  $$(".nav-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === view));
  $("#viewTitle").textContent = { dashboard: "总览", clients: "顾客档案", clientDetail: "客户病例中心", formulas: "配方库", export: "导出配方单" }[view];
  if (view === "export") renderFormulaSheet();
  if (view === "clientDetail") renderClientDetail();
}

function clientById(id) {
  return state.clients.find((client) => client.id === id);
}

function formulaTotals(formula) {
  const totalBags = Number(formula.dailyBags || 0) * Number(formula.days || 0);
  const singleWeight = (formula.ingredients || []).reduce((sum, item) => sum + Number(item.grams || 0), 0);
  return {
    totalBags,
    singleWeight,
    totalWeight: totalBags * singleWeight,
  };
}

function formatTimestamp(value) {
  if (!value) return "未记录";
  return new Date(Number(value) * 1000).toLocaleString("zh-CN", { hour12: false });
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function describeFormulaIngredients(formula) {
  return (formula.ingredients || []).map((item) => item.name).filter(Boolean).join("、");
}

function describeFormulaDosages(formula) {
  return (formula.ingredients || []).map((item) => `${item.name}${item.grams}g`).filter((item) => item.length > 1).join("，");
}

function fillConstitutionSelects() {
  const options = constitutions.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  $("#clientConstitution").insertAdjacentHTML("beforeend", options);
}

function resetClientForm() {
  $("#clientForm").reset();
  $("#clientId").value = "";
}

function resetFormulaForm() {
  $("#formulaForm").reset();
  $("#formulaId").value = "";
  $("#formulaClient").value = "";
  $("#dailyBags").value = 2;
  $("#days").value = 7;
  $("#waterMl").value = 350;
  $("#usage").value = "每日代茶温饮，饭后或两餐间饮用。";
  $("#ingredients").innerHTML = "";
  addIngredientRow("陈皮", 2);
  addIngredientRow("茯苓", 3);
  updateFormulaCalc();
}

function renderClientOptions() {
  const options = state.clients.map((client) => `<option value="${escapeHtml(client.id)}">${escapeHtml(client.name)} · ${escapeHtml(client.constitution || "未分类")}</option>`).join("");
  $("#formulaClient").innerHTML = `<option value="">配方库通用</option>` + options;
}

function renderClients() {
  const term = $("#clientSearch").value.trim().toLowerCase();
  const clients = state.clients.filter((client) => [client.name, client.gender, client.phone, client.constitution, client.concern, client.notes].join(" ").toLowerCase().includes(term));
  $("#clientList").innerHTML = clients.map((client) => `
    <article class="record">
      <div class="record-main">
        <div>
          <div class="record-title">${escapeHtml(client.name)} <span class="pill">${escapeHtml(client.constitution || "未分类")}</span></div>
          <div class="record-meta">${escapeHtml(client.gender || "性别未填")} · ${escapeHtml(client.age || "年龄未填")}岁 · ${escapeHtml(client.phone || "未留手机号")}</div>
          <div class="record-meta">${escapeHtml(client.concern || "暂无主诉")}</div>
        </div>
        <div class="record-actions">
          <button class="ghost-button small" data-edit-client="${escapeHtml(client.id)}" type="button">编辑</button>
          <button class="ghost-button small" data-view-client="${escapeHtml(client.id)}" type="button">查看详情</button>
          <button class="ghost-button small" data-plan-client="${escapeHtml(client.id)}" type="button">生成方案</button>
        </div>
      </div>
    </article>
  `).join("") || `<div class="empty-state">暂无顾客档案。</div>`;
}

function renderFormulas() {
  const term = $("#formulaSearch").value.trim().toLowerCase();
  const templates = state.formulaTemplates.filter((formula) => {
    return [
      formula.name,
      formula.category,
      formula.pattern,
      formula.audience,
      formula.composition,
      formula.defaultDosage,
      formula.modifications,
      formula.cautions,
      formula.notes,
    ].join(" ").toLowerCase().includes(term);
  });
  $("#formulaList").innerHTML = templates.map((formula) => {
    return `
      <article class="record">
        <div class="record-main">
          <div>
            <div class="record-title">${escapeHtml(formula.name)} <span class="pill status">${escapeHtml(formula.category || "未分类")}</span></div>
            <div class="record-meta">${escapeHtml(formula.pattern || "证型未填")} · ${escapeHtml(formula.audience || "人群未填")}</div>
            <div class="record-meta"><strong>组成：</strong>${escapeHtml(formula.composition || "未填写")}</div>
            <div class="record-meta"><strong>默认剂量：</strong>${escapeHtml(formula.defaultDosage || "未填写")}</div>
            <div class="record-meta"><strong>加减规则：</strong>${escapeHtml(formula.modifications || "未填写")}</div>
          </div>
          <div class="record-actions">
            <button class="ghost-button small" data-edit-formula="${escapeHtml(formula.id)}" type="button">编辑</button>
          </div>
        </div>
      </article>
    `;
  }).join("") || `<div class="empty-state">暂无配方模板。</div>`;
}

function renderDashboard() {
  $("#clientMetric").textContent = state.clients.length;
  $("#formulaMetric").textContent = state.formulaTemplates.length;
  $("#bagsMetric").textContent = state.formulas.reduce((sum, formula) => sum + formulaTotals(formula).totalBags, 0);
  $("#todayCount").textContent = state.formulas.filter((formula) => formula.status !== "已交付").length;

  const constitutionCounts = state.clients.reduce((acc, client) => {
    acc[client.constitution] = (acc[client.constitution] || 0) + 1;
    return acc;
  }, {});
  const sorted = Object.entries(constitutionCounts).sort((a, b) => b[1] - a[1]);
  $("#dominantMetric").textContent = sorted[0]?.[0] || "暂无";
  const max = sorted[0]?.[1] || 1;
  $("#constitutionBars").innerHTML = sorted.map(([name, count]) => `
    <div class="bar-row">
      <span>${escapeHtml(name)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(count / max) * 100}%"></div></div>
      <strong>${count}</strong>
    </div>
  `).join("") || `<div class="empty-state">建立顾客档案后显示体质分布。</div>`;

  $("#recentFormulas").innerHTML = state.formulas.slice(-5).reverse().map((formula) => {
    const client = clientById(formula.clientId);
    return `<div class="compact-item"><strong>${escapeHtml(formula.name)}</strong><span class="record-meta">${escapeHtml(client?.name || "未关联顾客")} · ${escapeHtml(formula.status)}</span></div>`;
  }).join("") || `<div class="empty-state">保存方案后会显示在这里。</div>`;
}

function renderExportOptions(selectedId) {
  $("#exportFormula").innerHTML = state.formulas.map((formula) => {
    const client = clientById(formula.clientId);
    return `<option value="${escapeHtml(formula.id)}">${escapeHtml(client?.name || "未关联顾客")} · ${escapeHtml(formula.name)}</option>`;
  }).join("") || `<option value="">暂无可导出方案</option>`;
  if (selectedId) $("#exportFormula").value = selectedId;
}

function renderAll() {
  renderClientOptions();
  renderFormulaLibraryOptions();
  renderClients();
  renderClientDetail();
  renderFormulas();
  renderDashboard();
  renderExportOptions($("#exportFormula").value);
  renderFormulaSheet();
}

function resetSessionForm() {
  $("#sessionForm").reset();
  $("#sessionDate").value = todayISO();
}

function resetClientFormulaForm() {
  $("#clientFormulaForm").reset();
  $("#clientFormulaDate").value = todayISO();
  renderClientFormulaSessionOptions();
}

function resetTodoForm() {
  $("#todoForm").reset();
  $("#todoId").value = "";
}

function sessionsForClient(clientId) {
  return state.clientSessions
    .filter((item) => item.clientId === clientId)
    .sort((a, b) => `${b.visitDate}-${b.createdAt}`.localeCompare(`${a.visitDate}-${a.createdAt}`));
}

function formulasForClient(clientId) {
  return state.clientFormulas
    .filter((item) => item.clientId === clientId)
    .sort((a, b) => `${b.formulaDate}-${b.createdAt}`.localeCompare(`${a.formulaDate}-${a.createdAt}`));
}

function todosForClient(clientId) {
  return state.clientTodos
    .filter((item) => item.clientId === clientId)
    .sort((a, b) => {
      if (a.isDone !== b.isDone) return a.isDone ? 1 : -1;
      return `${a.reminderDate || "9999-12-31"}-${a.createdAt}`.localeCompare(`${b.reminderDate || "9999-12-31"}-${b.createdAt}`);
    });
}

function viewClient(id) {
  state.selectedClientId = id;
  resetSessionForm();
  resetClientFormulaForm();
  resetTodoForm();
  setView("clientDetail");
}

function renderClientFormulaSessionOptions() {
  const select = $("#clientFormulaSession");
  if (!select) return;
  const sessions = sessionsForClient(state.selectedClientId);
  select.innerHTML = `<option value="">不关联回访记录</option>` + sessions.map((item) => (
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.visitDate)} · ${escapeHtml(item.complaintChange || "回访记录")}</option>`
  )).join("");
}

function renderFormulaLibraryOptions() {
  const select = $("#formulaLibrarySelect");
  if (!select) return;
  select.innerHTML = `<option value="">选择配方库方剂</option>` + state.formulaTemplates.map((formula) => {
    return `<option value="${escapeHtml(formula.id)}">${escapeHtml(formula.name)} · ${escapeHtml(formula.category || "通用")}</option>`;
  }).join("");
}

function fillClientFormulaForm(item, options = {}) {
  $("#clientFormulaDate").value = options.keepDate ? item.formulaDate : todayISO();
  $("#clientFormulaSession").value = item.clientSessionId || "";
  $("#clientFormulaName").value = options.copyName ? `${item.name}（复制）` : item.name;
  $("#clientFormulaHerbs").value = item.herbs || "";
  $("#clientFormulaDosages").value = item.dosages || "";
  $("#clientFormulaPreparation").value = item.preparation || "";
  $("#clientFormulaPeriod").value = item.period || "";
  $("#clientFormulaModifications").value = item.modifications || "";
  $("#clientFormulaCautions").value = item.cautions || "";
  $("#clientFormulaNotes").value = item.notes || "";
}

function applyFormulaLibrary() {
  const formula = state.formulaTemplates.find((item) => item.id === $("#formulaLibrarySelect").value);
  if (!formula) {
    toast("请选择要调用的配方");
    return;
  }
  fillClientFormulaForm({
    formulaDate: todayISO(),
    clientSessionId: "",
    name: formula.name,
    herbs: formula.composition || "",
    dosages: formula.defaultDosage || "",
    preparation: formula.usage || "",
    period: "",
    modifications: formula.modifications || "",
    cautions: formula.cautions || "",
    notes: [
      formula.pattern ? `适用证型：${formula.pattern}` : "",
      formula.audience ? `适用人群：${formula.audience}` : "",
      formula.tasteNotes ? `口感：${formula.tasteNotes}` : "",
      formula.notes ? `配方库备注：${formula.notes}` : "",
      "由配方库调用生成，可按本次情况加减。",
    ].filter(Boolean).join("\n"),
  });
  toast("已从配方库带入茶方草稿");
}

function renderClientDetail() {
  const panel = $("#clientDetailPanel");
  const timelineList = $("#clientTimeline");
  const list = $("#sessionList");
  const formulaList = $("#clientFormulaList");
  const todoList = $("#clientTodoList");
  if (!panel || !timelineList || !list || !formulaList || !todoList) return;

  const client = clientById(state.selectedClientId);
  if (!client) {
    panel.innerHTML = `<div class="empty-state">请先从顾客档案列表选择一位客户。</div>`;
    timelineList.innerHTML = `<div class="empty-state">暂无时间线记录。</div>`;
    list.innerHTML = `<div class="empty-state">暂无回访记录。</div>`;
    formulaList.innerHTML = `<div class="empty-state">暂无茶方记录。</div>`;
    todoList.innerHTML = `<div class="empty-state">暂无待办事项。</div>`;
    renderClientFormulaSessionOptions();
    return;
  }

  panel.innerHTML = `
    <div class="detail-header">
      <div>
        <h3>${escapeHtml(client.name)}</h3>
        <p class="record-meta">${escapeHtml(client.gender || "性别未填")} · ${escapeHtml(client.age || "年龄未填")}岁 · ${escapeHtml(client.phone || "未留手机号")}</p>
      </div>
      <span class="pill">${escapeHtml(client.constitution || "未分类")}</span>
    </div>
    <div class="detail-grid">
      <div><strong>主诉：</strong>${escapeHtml(client.concern || "未填写")}</div>
      <div><strong>备注：</strong>${escapeHtml(client.notes || "未填写")}</div>
      <div><strong>创建时间：</strong>${escapeHtml(formatTimestamp(client.createdAt))}</div>
    </div>
  `;

  const sessions = sessionsForClient(client.id);
  const clientFormulas = formulasForClient(client.id);
  const todos = todosForClient(client.id);
  renderClientFormulaSessionOptions();

  const timelineItems = [
    ...sessions.map((item) => ({ type: "回访", date: item.visitDate, createdAt: item.createdAt, item })),
    ...clientFormulas.map((item) => ({ type: "茶方", date: item.formulaDate, createdAt: item.createdAt, item })),
  ].sort((a, b) => `${b.date}-${b.createdAt}`.localeCompare(`${a.date}-${a.createdAt}`));

  timelineList.innerHTML = timelineItems.map(({ type, date, item }) => {
    if (type === "回访") {
      return `
        <article class="timeline-item">
          <div class="timeline-date">${escapeHtml(date)}</div>
          <div class="timeline-card">
            <div class="record-title">回访 <span class="pill">就诊记录</span></div>
            <div class="record-meta"><strong>主诉变化：</strong>${escapeHtml(item.complaintChange || "未填写")}</div>
            <div class="record-meta"><strong>调理建议：</strong>${escapeHtml(item.advice || "未填写")}</div>
          </div>
        </article>
      `;
    }
    return `
      <article class="timeline-item">
        <div class="timeline-date">${escapeHtml(date)}</div>
        <div class="timeline-card">
          <div class="record-title">${escapeHtml(item.name)} <span class="pill status">茶方</span></div>
          <div class="record-meta"><strong>药味：</strong>${escapeHtml(item.herbs || "未填写")}</div>
          <div class="record-meta"><strong>加减：</strong>${escapeHtml(item.modifications || "无")}</div>
        </div>
      </article>
    `;
  }).join("") || `<div class="empty-state">暂无时间线记录。</div>`;

  list.innerHTML = sessions.map((item) => `
    <article class="record">
      <div class="record-main">
        <div>
          <div class="record-title">${escapeHtml(item.visitDate)} <span class="pill status">回访</span></div>
          <div class="record-meta"><strong>主诉变化：</strong>${escapeHtml(item.complaintChange || "未填写")}</div>
          <div class="record-meta">睡眠：${escapeHtml(item.sleep || "未填写")} · 饮食：${escapeHtml(item.diet || "未填写")} · 大便：${escapeHtml(item.stool || "未填写")}</div>
          <div class="record-meta">舌象：${escapeHtml(item.tongue || "未填写")} · 脉象：${escapeHtml(item.pulse || "未填写")}</div>
          <div class="record-meta"><strong>调理建议：</strong>${escapeHtml(item.advice || "未填写")}</div>
          <div class="record-meta"><strong>备注：</strong>${escapeHtml(item.notes || "无")}</div>
        </div>
      </div>
    </article>
  `).join("") || `<div class="empty-state">暂无回访记录。</div>`;

  formulaList.innerHTML = clientFormulas.map((item) => {
    const linkedSession = item.clientSessionId ? state.clientSessions.find((session) => session.id === item.clientSessionId) : null;
    return `
      <article class="record">
        <div class="record-main">
          <div>
            <div class="record-title">${escapeHtml(item.name)} <span class="pill status">${escapeHtml(item.formulaDate)}</span></div>
            <div class="record-meta">${linkedSession ? `关联回访：${escapeHtml(linkedSession.visitDate)}` : "未关联回访记录"}</div>
            <div class="record-meta"><strong>药味组成：</strong>${escapeHtml(item.herbs || "未填写")}</div>
            <div class="record-meta"><strong>每味用量：</strong>${escapeHtml(item.dosages || "未填写")}</div>
            <div class="record-meta"><strong>煎服/冲泡：</strong>${escapeHtml(item.preparation || "未填写")}</div>
            <div class="record-meta"><strong>使用周期：</strong>${escapeHtml(item.period || "未填写")}</div>
            <div class="record-meta"><strong>加减说明：</strong>${escapeHtml(item.modifications || "无")}</div>
            <div class="record-meta"><strong>禁忌/注意：</strong>${escapeHtml(item.cautions || "无")}</div>
            <div class="record-meta"><strong>备注：</strong>${escapeHtml(item.notes || "无")}</div>
          </div>
          <div class="record-actions">
            <button class="ghost-button small" data-copy-client-formula="${escapeHtml(item.id)}" type="button">复制为新茶方</button>
          </div>
        </div>
      </article>
    `;
  }).join("") || `<div class="empty-state">暂无茶方记录。</div>`;

  todoList.innerHTML = todos.map((item) => `
    <article class="record ${item.isDone ? "is-done" : ""}">
      <div class="record-main">
        <div>
          <div class="record-title">${escapeHtml(item.content)} <span class="pill ${item.isDone ? "" : "status"}">${item.isDone ? "已完成" : "待处理"}</span></div>
          <div class="record-meta">提醒日期：${escapeHtml(item.reminderDate || "未设置")}</div>
          <div class="record-meta"><strong>备注：</strong>${escapeHtml(item.notes || "无")}</div>
        </div>
        <div class="record-actions">
          <button class="ghost-button small" data-toggle-todo="${escapeHtml(item.id)}" type="button">${item.isDone ? "标记未完成" : "完成"}</button>
        </div>
      </div>
    </article>
  `).join("") || `<div class="empty-state">暂无待办事项。</div>`;
}

function addIngredientRow(name = "", grams = "") {
  const row = document.createElement("div");
  row.className = "ingredient-row";
  row.innerHTML = `
    <input class="ingredient-name" placeholder="药材名称" value="${escapeHtml(name)}" />
    <input class="ingredient-grams" type="number" min="0" step="0.1" placeholder="克/包" value="${escapeHtml(grams)}" />
    <button class="icon-button" type="button" title="删除">×</button>
  `;
  row.querySelector(".icon-button").addEventListener("click", () => {
    row.remove();
    updateFormulaCalc();
  });
  row.querySelectorAll("input").forEach((input) => input.addEventListener("input", updateFormulaCalc));
  $("#ingredients").appendChild(row);
}

function readIngredients() {
  return $$("#ingredients .ingredient-row").map((row) => ({
    name: row.querySelector(".ingredient-name").value.trim(),
    grams: Number(row.querySelector(".ingredient-grams").value || 0),
  })).filter((item) => item.name && item.grams > 0);
}

function updateFormulaCalc() {
  const formula = {
    dailyBags: Number($("#dailyBags").value || 0),
    days: Number($("#days").value || 0),
    ingredients: readIngredients(),
  };
  const totals = formulaTotals(formula);
  $("#singleWeight").textContent = `${totals.singleWeight}g`;
  $("#totalBags").textContent = totals.totalBags;
  $("#totalWeight").textContent = `${totals.totalWeight}g`;
}

function editClient(id) {
  const client = clientById(id);
  if (!client) return;
  $("#clientId").value = client.id;
  $("#clientName").value = client.name;
  $("#clientGender").value = client.gender || "";
  $("#clientPhone").value = client.phone || "";
  $("#clientAge").value = client.age || "";
  $("#clientConstitution").value = client.constitution === "未分类" ? "" : client.constitution;
  $("#clientConcern").value = client.concern || "";
  $("#clientNotes").value = client.notes || "";
  setView("clients");
}

function editFormula(id) {
  const formula = state.formulaTemplates.find((item) => item.id === id);
  if (!formula) return;
  $("#formulaId").value = formula.id;
  $("#formulaClient").value = "";
  $("#formulaName").value = formula.name;
  $("#formulaCategory").value = formula.category || "";
  $("#formulaPattern").value = formula.pattern || "";
  $("#formulaAudience").value = formula.audience || "";
  $("#formulaComposition").value = formula.composition || "";
  $("#formulaDefaultDosage").value = formula.defaultDosage || "";
  $("#dailyBags").value = 1;
  $("#days").value = 1;
  $("#waterMl").value = 350;
  $("#formulaStatus").value = "待复核";
  $("#usage").value = formula.usage || "";
  $("#formulaModifications").value = formula.modifications || "";
  $("#cautions").value = formula.cautions || "";
  $("#formulaTasteNotes").value = formula.tasteNotes || "";
  $("#formulaCostNotes").value = formula.costNotes || "";
  $("#formulaNotes").value = formula.notes || "";
  $("#ingredients").innerHTML = "";
  updateFormulaCalc();
  setView("formulas");
}

function planForClient(id) {
  resetFormulaForm();
  $("#formulaClient").value = id;
  const client = clientById(id);
  $("#formulaName").value = `${client.constitution || "体质"}调理代茶饮`;
  setView("formulas");
}

function copyClientFormula(id) {
  const formula = state.clientFormulas.find((item) => item.id === id && item.clientId === state.selectedClientId);
  if (!formula) return;
  fillClientFormulaForm(formula, { copyName: true });
  $("#clientFormulaNotes").value = [formula.notes, "由历史茶方复制生成，请按本次情况加减。"].filter(Boolean).join("\n");
  toast("已复制为新茶方草稿");
}

async function toggleTodo(id) {
  const todo = state.clientTodos.find((item) => item.id === id && item.clientId === state.selectedClientId);
  if (!todo) return;
  await api(`/api/client-todos/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({ ...todo, isDone: !todo.isDone }),
  });
  await refreshData();
  renderClientDetail();
  toast(todo.isDone ? "待办已恢复为未完成" : "待办已完成");
}

function renderFormulaSheet() {
  const formula = state.formulas.find((item) => item.id === $("#exportFormula").value) || state.formulas[0];
  const sheet = $("#formulaSheet");
  if (!formula) {
    sheet.innerHTML = `<div class="empty-state">暂无配方单可导出。</div>`;
    return;
  }
  $("#exportFormula").value = formula.id;
  const client = clientById(formula.clientId) || {};
  const totals = formulaTotals(formula);
  sheet.innerHTML = `
    <div class="sheet-title">
      <div>
        <h3>${escapeHtml(formula.name)}</h3>
        <div class="record-meta">配方单编号：${escapeHtml(formula.id)}</div>
      </div>
      <div class="pill status">${escapeHtml(formula.status)}</div>
    </div>
    <div class="sheet-grid">
      <div><strong>顾客：</strong>${escapeHtml(client.name || "未填写")}</div>
      <div><strong>体质：</strong>${escapeHtml(client.constitution || "未填写")}</div>
      <div><strong>性别：</strong>${escapeHtml(client.gender || "未填写")}</div>
      <div><strong>年龄：</strong>${escapeHtml(client.age || "未填写")}</div>
      <div><strong>手机号：</strong>${escapeHtml(client.phone || "未填写")}</div>
      <div><strong>每日包数：</strong>${formula.dailyBags} 包</div>
      <div><strong>调理周期：</strong>${formula.days} 天</div>
      <div><strong>总包数：</strong>${totals.totalBags} 包</div>
      <div><strong>总克重：</strong>${totals.totalWeight}g</div>
    </div>
    <div class="sheet-block">
      <h4>配方组成</h4>
      <table>
        <thead><tr><th>名称</th><th>克/包</th><th>总克重</th></tr></thead>
        <tbody>
          ${formula.ingredients.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${item.grams}g</td><td>${item.grams * totals.totalBags}g</td></tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div class="sheet-block"><h4>用法</h4><p>${escapeHtml(formula.usage || "未填写")}</p><p>建议水量：每包 ${formula.waterMl || 350}ml。</p></div>
    <div class="sheet-block"><h4>顾客主诉</h4><p>${escapeHtml(client.concern || "未填写")}</p></div>
    <div class="sheet-block"><h4>注意事项</h4><p>${escapeHtml(formula.cautions || client.notes || "请按专业人员建议饮用，如有不适及时停用并咨询。")}</p></div>
  `;
}

function copyFormulaText() {
  const text = $("#formulaSheet").innerText.trim();
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => toast("配方单文本已复制"));
}

async function seedDemo() {
  if (state.clients.length || state.formulas.length) {
    toast("已有数据，未覆盖当前内容");
    return;
  }
  await api("/api/demo", { method: "POST", body: JSON.stringify({}) });
  await refreshData();
  toast("示例数据已载入");
}

async function logout() {
  await api("/api/logout", { method: "POST", body: JSON.stringify({}) });
  state.user = null;
  state.clients = [];
  state.formulas = [];
  state.formulaTemplates = [];
  state.clientSessions = [];
  state.clientFormulas = [];
  state.clientTodos = [];
  showLogin("已退出登录");
}

function bindEvents() {
  $$(".nav-tab").forEach((tab) => tab.addEventListener("click", () => setView(tab.dataset.view)));
  $$("[data-go]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.go)));
  $("#quickFormula").addEventListener("click", () => {
    resetFormulaForm();
    setView("formulas");
  });
  $("#seedDemo").addEventListener("click", seedDemo);
  $("#logoutButton").addEventListener("click", logout);
  $("#resetClient").addEventListener("click", resetClientForm);
  $("#backToClients").addEventListener("click", () => setView("clients"));
  $("#resetFormula").addEventListener("click", resetFormulaForm);
  $("#addIngredient").addEventListener("click", () => addIngredientRow());
  $("#applyFormulaLibrary").addEventListener("click", applyFormulaLibrary);
  ["dailyBags", "days"].forEach((id) => $(`#${id}`).addEventListener("input", updateFormulaCalc));
  $("#clientSearch").addEventListener("input", renderClients);
  $("#formulaSearch").addEventListener("input", renderFormulas);
  $("#exportFormula").addEventListener("change", renderFormulaSheet);
  $("#printFormula").addEventListener("click", () => window.print());
  $("#copyFormula").addEventListener("click", copyFormulaText);

  $("#loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("#loginMessage").textContent = "";
    try {
      const result = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({
          username: $("#loginUsername").value.trim(),
          password: $("#loginPassword").value,
        }),
      });
      state.user = result.user;
      showApp();
      await refreshData();
      toast("登录成功");
    } catch (error) {
      $("#loginMessage").textContent = error.message;
    }
  });

  $("#clientForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const id = $("#clientId").value || uid("client");
    const payload = {
      id,
      name: $("#clientName").value.trim(),
      gender: $("#clientGender").value,
      phone: $("#clientPhone").value.trim(),
      age: $("#clientAge").value,
      constitution: $("#clientConstitution").value || "未分类",
      concern: $("#clientConcern").value.trim(),
      notes: $("#clientNotes").value.trim(),
    };
    const exists = state.clients.some((client) => client.id === id);
    await api(exists ? `/api/clients/${encodeURIComponent(id)}` : "/api/clients", {
      method: exists ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    resetClientForm();
    await refreshData();
    toast("顾客档案已保存");
  });

  $("#sessionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const client = clientById(state.selectedClientId);
    if (!client) {
      toast("请先选择客户");
      return;
    }
    const payload = {
      id: uid("visit"),
      clientId: client.id,
      visitDate: $("#sessionDate").value,
      complaintChange: $("#sessionComplaintChange").value.trim(),
      sleep: $("#sessionSleep").value.trim(),
      diet: $("#sessionDiet").value.trim(),
      stool: $("#sessionStool").value.trim(),
      tongue: $("#sessionTongue").value.trim(),
      pulse: $("#sessionPulse").value.trim(),
      advice: $("#sessionAdvice").value.trim(),
      notes: $("#sessionNotes").value.trim(),
    };
    await api("/api/client-sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    resetSessionForm();
    await refreshData();
    renderClientDetail();
    toast("回访记录已保存");
  });

  $("#clientFormulaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const client = clientById(state.selectedClientId);
    if (!client) {
      toast("请先选择客户");
      return;
    }
    const payload = {
      id: uid("client_formula"),
      clientId: client.id,
      clientSessionId: $("#clientFormulaSession").value,
      formulaDate: $("#clientFormulaDate").value,
      name: $("#clientFormulaName").value.trim(),
      herbs: $("#clientFormulaHerbs").value.trim(),
      dosages: $("#clientFormulaDosages").value.trim(),
      preparation: $("#clientFormulaPreparation").value.trim(),
      period: $("#clientFormulaPeriod").value.trim(),
      modifications: $("#clientFormulaModifications").value.trim(),
      cautions: $("#clientFormulaCautions").value.trim(),
      notes: $("#clientFormulaNotes").value.trim(),
    };
    await api("/api/client-formulas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    resetClientFormulaForm();
    await refreshData();
    renderClientDetail();
    toast("茶方记录已保存");
  });

  $("#todoForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const client = clientById(state.selectedClientId);
    if (!client) {
      toast("请先选择客户");
      return;
    }
    const id = $("#todoId").value || uid("client_todo");
    const existing = state.clientTodos.find((item) => item.id === id);
    const payload = {
      id,
      clientId: client.id,
      content: $("#todoContent").value.trim(),
      reminderDate: $("#todoReminderDate").value,
      isDone: existing?.isDone || false,
      notes: $("#todoNotes").value.trim(),
    };
    await api(existing ? `/api/client-todos/${encodeURIComponent(id)}` : "/api/client-todos", {
      method: existing ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    resetTodoForm();
    await refreshData();
    renderClientDetail();
    toast("待办事项已保存");
  });

  $("#formulaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!$("#formulaComposition").value.trim()) {
      toast("请填写组成");
      return;
    }
    const id = $("#formulaId").value || uid("formula_template");
    const payload = {
      id,
      name: $("#formulaName").value.trim(),
      category: $("#formulaCategory").value.trim(),
      pattern: $("#formulaPattern").value.trim(),
      audience: $("#formulaAudience").value.trim(),
      composition: $("#formulaComposition").value.trim(),
      defaultDosage: $("#formulaDefaultDosage").value.trim(),
      usage: $("#usage").value.trim(),
      modifications: $("#formulaModifications").value.trim(),
      cautions: $("#cautions").value.trim(),
      tasteNotes: $("#formulaTasteNotes").value.trim(),
      costNotes: $("#formulaCostNotes").value.trim(),
      notes: $("#formulaNotes").value.trim(),
    };
    const exists = state.formulaTemplates.some((formula) => formula.id === id);
    await api(exists ? `/api/formula-templates/${encodeURIComponent(id)}` : "/api/formula-templates", {
      method: exists ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    await refreshData();
    toast("配方模板已保存");
  });

  document.addEventListener("click", (event) => {
    const editClientId = event.target.dataset.editClient;
    const viewClientId = event.target.dataset.viewClient;
    const planClientId = event.target.dataset.planClient;
    const editFormulaId = event.target.dataset.editFormula;
    const exportFormulaId = event.target.dataset.exportFormula;
    const copyClientFormulaId = event.target.dataset.copyClientFormula;
    const toggleTodoId = event.target.dataset.toggleTodo;
    if (editClientId) editClient(editClientId);
    if (viewClientId) viewClient(viewClientId);
    if (planClientId) planForClient(planClientId);
    if (editFormulaId) editFormula(editFormulaId);
    if (copyClientFormulaId) copyClientFormula(copyClientFormulaId);
    if (toggleTodoId) toggleTodo(toggleTodoId);
    if (exportFormulaId) {
      renderExportOptions(exportFormulaId);
      setView("export");
    }
  });
}

async function boot() {
  fillConstitutionSelects();
  bindEvents();
  resetFormulaForm();
  try {
    const session = await api("/api/session");
    state.user = session.user;
    showApp();
    await refreshData();
  } catch {
    showLogin();
  }
}

boot();
