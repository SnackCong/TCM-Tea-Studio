const constitutions = ["平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"];

const state = {
  clients: [],
  formulas: [],
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
  renderAll();
}

function setView(view) {
  state.currentView = view;
  $$(".view").forEach((el) => el.classList.remove("active"));
  $(`#${view}View`).classList.add("active");
  $$(".nav-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === view));
  $("#viewTitle").textContent = { dashboard: "总览", clients: "顾客档案", formulas: "茶包方案", export: "导出配方单" }[view];
  if (view === "export") renderFormulaSheet();
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
  const options = state.clients.map((client) => `<option value="${escapeHtml(client.id)}">${escapeHtml(client.name)} · ${escapeHtml(client.constitution)}</option>`).join("");
  $("#formulaClient").innerHTML = options || `<option value="">请先建立顾客档案</option>`;
}

function renderClients() {
  const term = $("#clientSearch").value.trim().toLowerCase();
  const clients = state.clients.filter((client) => [client.name, client.phone, client.constitution, client.concern].join(" ").toLowerCase().includes(term));
  $("#clientList").innerHTML = clients.map((client) => `
    <article class="record">
      <div class="record-main">
        <div>
          <div class="record-title">${escapeHtml(client.name)} <span class="pill">${escapeHtml(client.constitution)}</span></div>
          <div class="record-meta">${escapeHtml(client.phone || "未留手机号")} · ${escapeHtml(client.age || "年龄未填")}岁</div>
          <div class="record-meta">${escapeHtml(client.concern || "暂无主诉")}</div>
        </div>
        <div class="record-actions">
          <button class="ghost-button small" data-edit-client="${escapeHtml(client.id)}" type="button">编辑</button>
          <button class="ghost-button small" data-plan-client="${escapeHtml(client.id)}" type="button">生成方案</button>
        </div>
      </div>
    </article>
  `).join("") || `<div class="empty-state">暂无顾客档案。</div>`;
}

function renderFormulas() {
  const term = $("#formulaSearch").value.trim().toLowerCase();
  const formulas = state.formulas.filter((formula) => {
    const client = clientById(formula.clientId);
    return [formula.name, formula.status, client?.name, client?.constitution].join(" ").toLowerCase().includes(term);
  });
  $("#formulaList").innerHTML = formulas.map((formula) => {
    const client = clientById(formula.clientId);
    const totals = formulaTotals(formula);
    return `
      <article class="record">
        <div class="record-main">
          <div>
            <div class="record-title">${escapeHtml(formula.name)} <span class="pill status">${escapeHtml(formula.status)}</span></div>
            <div class="record-meta">${escapeHtml(client?.name || "未关联顾客")} · ${escapeHtml(client?.constitution || "体质未填")}</div>
            <div class="record-meta">${totals.totalBags} 包 · 单包 ${totals.singleWeight}g · 总量 ${totals.totalWeight}g</div>
          </div>
          <div class="record-actions">
            <button class="ghost-button small" data-edit-formula="${escapeHtml(formula.id)}" type="button">编辑</button>
            <button class="ghost-button small" data-export-formula="${escapeHtml(formula.id)}" type="button">导出</button>
          </div>
        </div>
      </article>
    `;
  }).join("") || `<div class="empty-state">暂无茶包方案。</div>`;
}

function renderDashboard() {
  $("#clientMetric").textContent = state.clients.length;
  $("#formulaMetric").textContent = state.formulas.length;
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
  renderClients();
  renderFormulas();
  renderDashboard();
  renderExportOptions($("#exportFormula").value);
  renderFormulaSheet();
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
  $("#clientPhone").value = client.phone || "";
  $("#clientAge").value = client.age || "";
  $("#clientConstitution").value = client.constitution;
  $("#clientConcern").value = client.concern || "";
  $("#clientNotes").value = client.notes || "";
  setView("clients");
}

function editFormula(id) {
  const formula = state.formulas.find((item) => item.id === id);
  if (!formula) return;
  $("#formulaId").value = formula.id;
  $("#formulaClient").value = formula.clientId;
  $("#formulaName").value = formula.name;
  $("#dailyBags").value = formula.dailyBags;
  $("#days").value = formula.days;
  $("#waterMl").value = formula.waterMl;
  $("#formulaStatus").value = formula.status;
  $("#usage").value = formula.usage || "";
  $("#cautions").value = formula.cautions || "";
  $("#ingredients").innerHTML = "";
  formula.ingredients.forEach((item) => addIngredientRow(item.name, item.grams));
  updateFormulaCalc();
  setView("formulas");
}

function planForClient(id) {
  resetFormulaForm();
  $("#formulaClient").value = id;
  const client = clientById(id);
  $("#formulaName").value = `${client.constitution}调理代茶饮`;
  setView("formulas");
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
  $("#resetFormula").addEventListener("click", resetFormulaForm);
  $("#addIngredient").addEventListener("click", () => addIngredientRow());
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
      phone: $("#clientPhone").value.trim(),
      age: $("#clientAge").value,
      constitution: $("#clientConstitution").value,
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

  $("#formulaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const ingredients = readIngredients();
    if (!ingredients.length) {
      toast("请至少添加一味材料");
      return;
    }
    const id = $("#formulaId").value || uid("formula");
    const payload = {
      id,
      clientId: $("#formulaClient").value,
      name: $("#formulaName").value.trim(),
      dailyBags: Number($("#dailyBags").value),
      days: Number($("#days").value),
      waterMl: Number($("#waterMl").value),
      status: $("#formulaStatus").value,
      usage: $("#usage").value.trim(),
      cautions: $("#cautions").value.trim(),
      ingredients,
    };
    const exists = state.formulas.some((formula) => formula.id === id);
    await api(exists ? `/api/formulas/${encodeURIComponent(id)}` : "/api/formulas", {
      method: exists ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    await refreshData();
    toast("茶包方案已保存");
  });

  document.addEventListener("click", (event) => {
    const editClientId = event.target.dataset.editClient;
    const planClientId = event.target.dataset.planClient;
    const editFormulaId = event.target.dataset.editFormula;
    const exportFormulaId = event.target.dataset.exportFormula;
    if (editClientId) editClient(editClientId);
    if (planClientId) planForClient(planClientId);
    if (editFormulaId) editFormula(editFormulaId);
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
