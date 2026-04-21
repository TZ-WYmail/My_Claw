/* LocalCommandCenter — 前端逻辑 v2 */
const API = "";

// ============================================================
// 工具函数
// ============================================================

async function apiPost(endpoint, body) {
    const resp = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return resp.json();
}

async function apiGet(endpoint) {
    const resp = await fetch(`${API}${endpoint}`);
    return resp.json();
}

function toast(msg, type = "info") {
    let c = document.querySelector(".toast-container");
    if (!c) { c = document.createElement("div"); c.className = "toast-container"; document.body.appendChild(c); }
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    c.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function formatTime(iso) {
    if (!iso) return "-";
    try {
        const d = new Date(iso);
        const w = ["周日","周一","周二","周三","周四","周五","周六"];
        return `${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ` +
               `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")} (${w[d.getDay()]})`;
    } catch { return iso; }
}

function formatTimeShort(iso) {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN", {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}); }
    catch { return iso; }
}

function escapeHtml(str) {
    const d = document.createElement("div"); d.textContent = str; return d.innerHTML;
}

const RECURRENCE_MAP = { once:"一次", daily:"每天", weekly:"每周", monthly:"每月" };

// ============================================================
// 主题切换
// ============================================================

function initTheme() {
    const saved = localStorage.getItem("lcc-theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    updateThemeBtn(saved);
}

function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("lcc-theme", next);
    updateThemeBtn(next);
}

function updateThemeBtn(theme) {
    const btn = document.getElementById("btn-theme");
    if (btn) btn.textContent = theme === "dark" ? "🌙" : "☀️";
}

initTheme();
document.getElementById("btn-theme")?.addEventListener("click", toggleTheme);

// ============================================================
// 标签页切换
// ============================================================

document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
    });
});

// 内标签页切换
document.querySelectorAll(".inner-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        const parent = tab.closest(".card");
        parent.querySelectorAll(".inner-tab").forEach(t => t.classList.remove("active"));
        parent.querySelectorAll(".inner-panel").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        parent.querySelector(`#inner-${tab.dataset.inner}`).classList.add("active");
        // 触发数据加载
        if (tab.dataset.inner === "all") loadAllTasks();
        if (tab.dataset.inner === "dl-history") loadDownloadHistory();
    });
});

// ============================================================
// 健康检查
// ============================================================

async function checkHealth() {
    try {
        const data = await apiGet("/health");
        document.getElementById("status-dot").className = "status-dot connected";
        document.getElementById("status-text").textContent = `${data.service} v${data.version}`;
    } catch {
        document.getElementById("status-dot").className = "status-dot error";
        document.getElementById("status-text").textContent = "连接失败";
    }
}
checkHealth();
setInterval(checkHealth, 30000);

// ============================================================
// 仪表盘 Dashboard
// ============================================================

async function loadDashboard() {
    try {
        const data = await apiGet("/api/dashboard");
        if (data.status !== "success") return;

        // 统计卡片
        document.getElementById("stat-tasks-pending").textContent = data.tasks?.pending ?? 0;
        document.getElementById("stat-tasks-completed").textContent = data.tasks?.completed ?? 0;
        document.getElementById("stat-downloads").textContent = data.downloads?.total ?? 0;
        document.getElementById("stat-storage").textContent = data.storage?.total_size ?? "0 B";

        // 最近下载
        const dlEl = document.getElementById("dash-recent-downloads");
        if (data.recent_downloads && data.recent_downloads.length > 0) {
            dlEl.innerHTML = data.recent_downloads.map(d => `
                <div class="activity-item">
                    <span class="activity-icon">📥</span>
                    <span class="activity-text">${escapeHtml(d.filename || d.url)}</span>
                    <span class="activity-time">${formatTimeShort(d.created_at)}</span>
                </div>
            `).join("");
        } else {
            dlEl.innerHTML = '<div class="empty-state">暂无下载记录</div>';
        }

        // 最近操作
        const logEl = document.getElementById("dash-recent-logs");
        if (data.recent_logs && data.recent_logs.length > 0) {
            logEl.innerHTML = data.recent_logs.map(l => `
                <div class="activity-item">
                    <span class="activity-icon">${operationIcon(l.operation)}</span>
                    <span class="activity-text">${escapeHtml(l.operation)}</span>
                    <span class="activity-time">${formatTimeShort(l.created_at)}</span>
                </div>
            `).join("");
        } else {
            logEl.innerHTML = '<div class="empty-state">暂无操作记录</div>';
        }
    } catch (e) {
        console.error("Dashboard load error:", e);
    }
}

function operationIcon(op) {
    const map = { task_add:"📋", task_complete:"✅", task_delete:"🗑️", download:"📥", download_async:"⏳", sandbox:"🔧", search:"🔍" };
    return map[op] || "📜";
}

loadDashboard();

// ============================================================
// 任务管理
// ============================================================

// 弹窗
function openModal() { document.getElementById("modal-overlay").style.display = "flex"; }
function closeModal() { document.getElementById("modal-overlay").style.display = "none"; }

document.getElementById("btn-add-task-modal")?.addEventListener("click", openModal);

document.getElementById("btn-modal-add-task")?.addEventListener("click", async () => {
    const name = document.getElementById("modal-task-name").value.trim();
    const due = document.getElementById("modal-task-due").value;
    const recurrence = document.getElementById("modal-task-recurrence").value;

    if (!name) return toast("请输入任务名称", "error");
    if (!due) return toast("请选择截止时间", "error");

    const dueISO = new Date(due).toISOString();
    const res = await apiPost("/api/task", { action: "add_task", task_name: name, due_time: dueISO, recurrence });

    if (res.status === "success") {
        toast(`任务「${name}」已添加`, "success");
        closeModal();
        document.getElementById("modal-task-name").value = "";
        loadWeeklyPlan();
        loadDashboard();
    } else {
        toast(res.message || "添加失败", "error");
    }
});

// 周计划 — 带时间纵轴的周日历
let calWeekOffset = 0; // 0=本周, -1=上周, 1=下周
const WC_HOURS_START = 7;  // 起始时间
const WC_HOURS_END = 23;   // 结束时间

async function loadWeeklyPlan(offset) {
    if (offset !== undefined) calWeekOffset = offset;

    try {
        // 计算当前显示周的日期范围
        const now = new Date();
        const monday = new Date(now);
        monday.setDate(now.getDate() - ((now.getDay() + 6) % 7) + calWeekOffset * 7);
        monday.setHours(0, 0, 0, 0);

        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        sunday.setHours(23, 59, 59, 0);

        const mondayStr = `${monday.getFullYear()}-${String(monday.getMonth()+1).padStart(2,"0")}-${String(monday.getDate()).padStart(2,"0")}T00:00:00`;
        const sundayStr = `${sunday.getFullYear()}-${String(sunday.getMonth()+1).padStart(2,"0")}-${String(sunday.getDate()).padStart(2,"0")}T23:59:59`;

        // 传递日期范围给后端
        const res = await apiPost("/api/task", {
            action: "get_weekly_plan",
            due_time: mondayStr,
            task_name: sundayStr,
        });

        // 更新标签
        const label = document.getElementById("cal-week-label");
        if (label) {
            const fmt = d => `${d.getMonth()+1}/${d.getDate()}`;
            label.textContent = calWeekOffset === 0
                ? `本周 (${fmt(monday)} - ${fmt(sunday)})`
                : `${fmt(monday)} - ${fmt(sunday)}`;
        }

        const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
        const todayDayIdx = calWeekOffset === 0 ? (now.getDay() + 6) % 7 : -1;
        const dayNames = ["周一","周二","周三","周四","周五","周六","周日"];

        // 构建任务映射: { "dayIdx-hour": [tasks] }
        const taskMap = {};
        if (res.tasks && res.tasks.length > 0) {
            res.tasks.forEach(t => {
                try {
                    const td = new Date(t.due_time);
                    for (let i = 0; i < 7; i++) {
                        const dd = new Date(monday);
                        dd.setDate(monday.getDate() + i);
                        const dayStr = `${dd.getFullYear()}-${String(dd.getMonth()+1).padStart(2,"0")}-${String(dd.getDate()).padStart(2,"0")}`;
                        const taskDayStr = `${td.getFullYear()}-${String(td.getMonth()+1).padStart(2,"0")}-${String(td.getDate()).padStart(2,"0")}`;
                        if (dayStr === taskDayStr) {
                            const hour = td.getHours();
                            const key = `${i}-${hour}`;
                            if (!taskMap[key]) taskMap[key] = [];
                            taskMap[key].push(t);
                            break;
                        }
                    }
                } catch {}
            });
        }

        // 构建 HTML
        let html = '<div class="wc-header-row">';
        html += '<div class="wc-corner"></div>';
        for (let i = 0; i < 7; i++) {
            const dd = new Date(monday);
            dd.setDate(monday.getDate() + i);
            const dateLabel = `${dd.getMonth()+1}/${dd.getDate()}`;
            const isToday = i === todayDayIdx;
            html += `<div class="wc-day-header${isToday ? " today-col" : ""}">${dayNames[i]}<br><span style="font-weight:400;font-size:0.7rem">${dateLabel}</span></div>`;
        }
        html += '</div>';

        // 时间行
        for (let h = WC_HOURS_START; h <= WC_HOURS_END; h++) {
            html += `<div class="wc-time-row">`;
            html += `<div class="wc-time-label">${String(h).padStart(2,"0")}:00</div>`;
            for (let i = 0; i < 7; i++) {
                const isToday = i === todayDayIdx;
                const key = `${i}-${h}`;
                const tasks = taskMap[key] || [];
                html += `<div class="wc-cell${isToday ? " is-today-col" : ""}">`;
                tasks.forEach(t => {
                    const m = new Date(t.due_time).getMinutes();
                    const timeStr = `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
                    const cls = t.status === "已完成" ? "status-completed" : "status-pending";
                    html += `<div class="wc-task ${cls}" title="${escapeHtml(t.task_name)} ${timeStr}">`;
                    html += `<span class="wc-task-name">${escapeHtml(t.task_name)}</span>`;
                    html += `<span class="wc-task-actions">`;
                    if (t.status === "待执行") html += `<button class="wc-btn wc-btn-done" onclick="event.stopPropagation();completeTask('${t.task_id}')">✓</button>`;
                    html += `<button class="wc-btn wc-btn-del" onclick="event.stopPropagation();deleteTask('${t.task_id}')">✕</button>`;
                    html += `</span></div>`;
                });
                html += `</div>`;
            }
            html += `</div>`;
        }

        const container = document.getElementById("week-calendar");
        if (container) {
            container.innerHTML = html;
            // 自动滚动到当前时间附近
            if (calWeekOffset === 0) {
                const currentHour = now.getHours();
                const scrollToHour = Math.max(WC_HOURS_START, currentHour - 1);
                const rowHeight = 48;
                container.scrollTop = (scrollToHour - WC_HOURS_START) * rowHeight;
            }
        }

    } catch (e) { toast("加载周计划失败", "error"); }
}

// 日历导航
document.getElementById("cal-prev")?.addEventListener("click", () => loadWeeklyPlan(calWeekOffset - 1));
document.getElementById("cal-next")?.addEventListener("click", () => loadWeeklyPlan(calWeekOffset + 1));
document.getElementById("cal-today")?.addEventListener("click", () => loadWeeklyPlan(0));

// 全部任务
let allTaskPage = 1;
async function loadAllTasks(page) {
    if (page) allTaskPage = page;
    const status = document.getElementById("task-status-filter")?.value || "active";
    const keyword = document.getElementById("task-search")?.value?.trim() || "";
    try {
        const params = new URLSearchParams({ status, keyword, page: allTaskPage, page_size: 20 });
        const data = await apiGet(`/api/tasks/all?${params}`);
        const tbody = document.getElementById("all-task-tbody");
        if (!data.tasks || data.tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty">无匹配任务</td></tr>';
        } else {
            tbody.innerHTML = data.tasks.map((t, i) => {
                const idx = (allTaskPage - 1) * 20 + i + 1;
                return `<tr>
                    <td>${idx}</td>
                    <td>${escapeHtml(t.task_name)}</td>
                    <td>${formatTime(t.due_time)}</td>
                    <td>${RECURRENCE_MAP[t.recurrence] || t.recurrence}</td>
                    <td><span class="badge badge-${badgeClass(t.status)}">${t.status}</span></td>
                    <td>${formatTimeShort(t.created_at)}</td>
                    <td>${taskActions(t)}</td>
                </tr>`;
            }).join("");
        }
        renderPagination("task-pagination", allTaskPage, Math.ceil((data.total||0)/20), loadAllTasks);
    } catch (e) { toast("加载任务列表失败", "error"); }
}

function badgeClass(status) {
    if (status === "已完成") return "completed";
    if (status === "已删除") return "error";
    return "pending";
}

function taskActions(t) {
    let html = '';
    if (t.status === "待执行") html += `<button class="btn btn-success" onclick="completeTask('${t.task_id}')">完成</button> `;
    if (t.status !== "已删除") html += `<button class="btn btn-danger" onclick="deleteTask('${t.task_id}')">删除</button>`;
    return html;
}

async function completeTask(id) {
    const res = await apiPost("/api/task", { action: "complete_task", task_id: id });
    if (res.status === "success") { toast("任务已完成", "success"); loadWeeklyPlan(); loadDashboard(); }
    else toast(res.message, "error");
}

async function deleteTask(id) {
    if (!confirm("确定删除此任务？")) return;
    const res = await apiPost("/api/task", { action: "delete_task", task_id: id });
    if (res.status === "success") { toast("任务已删除", "success"); loadWeeklyPlan(); loadDashboard(); }
    else toast(res.message, "error");
}

// 搜索 & 筛选
document.getElementById("task-search")?.addEventListener("input", () => loadAllTasks(1));
document.getElementById("task-status-filter")?.addEventListener("change", () => loadAllTasks(1));

loadWeeklyPlan();

// ============================================================
// 下载中心
// ============================================================

document.getElementById("btn-download")?.addEventListener("click", async () => {
    const url = document.getElementById("dl-url").value.trim();
    const category = document.getElementById("dl-category").value;
    const filename = document.getElementById("dl-filename").value.trim() || undefined;

    if (!url) return toast("请输入下载 URL", "error");

    const btn = document.getElementById("btn-download");
    btn.disabled = true; btn.textContent = "下载中...";

    try {
        const res = await apiPost("/api/download", { url, category, filename });
        const box = document.getElementById("download-result");
        const out = document.getElementById("download-output");
        box.style.display = "block";

        if (res.mode === "async") {
            out.textContent = `⏳ 异步下载中\n任务ID: ${res.job_id}\n预估耗时: ~${res.estimated_seconds}秒\n\n在此期间可以做其他操作，稍后用沙盒区的异步查询查看进度。`;
            toast(`大文件后台下载中，ID: ${res.job_id}`, "info");
            document.getElementById("job-id").value = res.job_id;
        } else if (res.status === "success") {
            out.textContent = `📥 下载完成\n文件: ${res.file_path}\n大小: ${res.file_size}\n安全扫描: ${res.security_scan === "passed" ? "✅ 通过" : "❌ " + res.security_scan}\n分类: ${category}`;
            toast("下载完成", "success");
            loadDashboard();
        } else {
            out.textContent = `❌ 下载失败: ${res.message}`;
            toast(res.message, "error");
        }
    } catch (e) { toast("网络错误: " + e.message, "error"); }

    btn.disabled = false; btn.textContent = "开始下载";
});

// 下载历史
let dlHistoryPage = 1;
async function loadDownloadHistory(page) {
    if (page) dlHistoryPage = page;
    const cat = document.getElementById("dl-history-cat")?.value || "";
    try {
        const params = new URLSearchParams({ category: cat, page: dlHistoryPage, page_size: 20 });
        const data = await apiGet(`/api/download/history?${params}`);
        const tbody = document.getElementById("dl-history-tbody");
        if (!data.records || data.records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty">暂无下载记录</td></tr>';
        } else {
            tbody.innerHTML = data.records.map((r, i) => `<tr>
                <td>${(dlHistoryPage-1)*20+i+1}</td>
                <td title="${escapeHtml(r.file_path||"")}">${escapeHtml(r.filename||"-")}</td>
                <td>${r.category||"-"}</td>
                <td>${r.file_size||"-"}</td>
                <td>${r.security_scan === "passed" ? "✅" : r.security_scan === "failed" ? "❌" : "-"}</td>
                <td><span class="badge badge-${r.status==='success'?'completed':'error'}">${r.status||"-"}</span></td>
                <td>${formatTimeShort(r.created_at)}</td>
                <td title="${escapeHtml(r.url||"")}">${(r.url||"-").substring(0,40)}${(r.url||"").length>40?"...":""}</td>
            </tr>`).join("");
        }
        renderPagination("dl-history-pagination", dlHistoryPage, Math.ceil((data.total||0)/20), loadDownloadHistory);
    } catch (e) { toast("加载下载历史失败", "error"); }
}

document.getElementById("dl-history-cat")?.addEventListener("change", () => loadDownloadHistory(1));

// ============================================================
// 文件检索
// ============================================================

document.getElementById("btn-search")?.addEventListener("click", async () => {
    const keyword = document.getElementById("search-keyword").value.trim();
    const category = document.getElementById("search-category").value;
    try {
        const res = await apiPost("/api/search", { keyword, category });
        const tbody = document.getElementById("search-tbody");
        const countEl = document.getElementById("search-count");
        if (!res.files || res.files.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty">无匹配文件</td></tr>';
            countEl.textContent = "";
        } else {
            countEl.textContent = `(${res.total} 条)`;
            tbody.innerHTML = res.files.map((f, i) => `<tr>
                <td>${i+1}</td>
                <td title="${escapeHtml(f.path)}">${escapeHtml(f.filename)}</td>
                <td>${f.category}</td>
                <td>${f.size}</td>
                <td>${f.downloaded_at ? f.downloaded_at.replace("T"," ").slice(0,16) : "-"}</td>
                <td class="path-cell" title="${escapeHtml(f.path)}">${escapeHtml(f.path)}</td>
            </tr>`).join("");
        }
    } catch (e) { toast("搜索失败: " + e.message, "error"); }
});

// ============================================================
// 沙盒执行
// ============================================================

document.getElementById("btn-sandbox")?.addEventListener("click", async () => {
    const tool_name = document.getElementById("sb-tool").value;
    const execution_command = document.getElementById("sb-cmd").value.trim();
    const setupRaw = document.getElementById("sb-setup").value.trim();
    const filesRaw = document.getElementById("sb-files").value.trim();

    if (!execution_command) return toast("请输入执行命令", "error");

    const setup_commands = setupRaw ? setupRaw.split("\n").filter(l => l.trim()) : undefined;
    let dynamic_files = undefined;
    if (filesRaw) { try { dynamic_files = JSON.parse(filesRaw); } catch { return toast("JSON 格式错误", "error"); } }

    const btn = document.getElementById("btn-sandbox");
    btn.disabled = true; btn.textContent = "执行中...";

    try {
        const res = await apiPost("/api/sandbox", { tool_name, execution_command, setup_commands, dynamic_files });
        const box = document.getElementById("sandbox-result");
        const out = document.getElementById("sandbox-output");
        box.style.display = "block";

        let text = `🔧 沙盒执行${res.status==="success"?"成功":"失败"}\n工具: ${tool_name}\n命令: ${execution_command}\n耗时: ${res.duration_seconds||"-"}秒\n\n`;
        if (res.stdout) text += `--- stdout ---\n${res.stdout}\n\n`;
        if (res.stderr) text += `--- stderr ---\n${res.stderr}\n`;
        if (res.copied_to?.length) text += `\n输出文件: ${res.copied_to.join(", ")}`;
        out.textContent = text;

        if (res.status === "success") { toast("执行完成", "success"); loadDashboard(); }
        else toast("执行失败", "error");
    } catch (e) { toast("网络错误: " + e.message, "error"); }

    btn.disabled = false; btn.textContent = "执行";
});

// 异步任务查询
document.getElementById("btn-job-status")?.addEventListener("click", async () => {
    const job_id = document.getElementById("job-id").value.trim();
    if (!job_id) return toast("请输入任务 ID", "error");
    try {
        const res = await apiPost("/api/job/status", { job_id });
        const box = document.getElementById("sandbox-result");
        const out = document.getElementById("sandbox-output");
        box.style.display = "block";
        out.textContent = JSON.stringify(res, null, 2);
    } catch (e) { toast("查询失败: " + e.message, "error"); }
});

// ============================================================
// 操作日志
// ============================================================

let logsPage = 1;
async function loadLogs(page) {
    if (page) logsPage = page;
    const op = document.getElementById("log-operation-filter")?.value || "";
    try {
        const params = new URLSearchParams({ operation: op, page: logsPage, page_size: 50 });
        const data = await apiGet(`/api/logs?${params}`);
        const tbody = document.getElementById("logs-tbody");
        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无操作日志</td></tr>';
        } else {
            tbody.innerHTML = data.logs.map((l, i) => `<tr>
                <td>${(logsPage-1)*50+i+1}</td>
                <td>${operationIcon(l.operation)} ${escapeHtml(l.operation)}</td>
                <td>${escapeHtml(l.endpoint||"-")}</td>
                <td class="cell-truncate" title="${escapeHtml(l.params||"")}">${escapeHtml((l.params||"").substring(0,50))}</td>
                <td><span class="badge badge-${l.result==='success'?'completed':'error'}">${l.result||"-"}</span></td>
                <td class="cell-truncate" title="${escapeHtml(l.detail||"")}">${escapeHtml((l.detail||"").substring(0,60))}</td>
                <td>${formatTimeShort(l.created_at)}</td>
            </tr>`).join("");
        }
        renderPagination("logs-pagination", logsPage, Math.ceil((data.total||0)/50), loadLogs);
    } catch (e) { toast("加载日志失败", "error"); }
}

document.getElementById("log-operation-filter")?.addEventListener("change", () => loadLogs(1));
document.getElementById("btn-refresh-logs")?.addEventListener("click", () => loadLogs(1));

loadLogs();

// ============================================================
// 分页组件
// ============================================================

function renderPagination(containerId, current, totalPages, onPageFn) {
    const el = document.getElementById(containerId);
    if (!el || totalPages <= 1) { if (el) el.innerHTML = ""; return; }

    // 存回调到全局 map
    const fnKey = `pgFn_${containerId}`;
    window[fnKey] = onPageFn;

    let html = "";
    html += `<button class="btn btn-sm" ${current<=1?"disabled":""} onclick="window['${fnKey}'](${current-1})">上一页</button>`;
    html += `<span class="page-info">${current} / ${totalPages}</span>`;
    html += `<button class="btn btn-sm" ${current>=totalPages?"disabled":""} onclick="window['${fnKey}'](${current+1})">下一页</button>`;
    el.innerHTML = html;
}

// ============================================================
// 全局搜索 (Ctrl+K)
// ============================================================

const searchInput = document.getElementById("global-search");
const searchDropdown = document.getElementById("search-dropdown");

document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        searchInput?.focus();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        openModal();
    }
});

let searchTimer = null;
searchInput?.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (!q) { searchDropdown.style.display = "none"; return; }
    searchTimer = setTimeout(async () => {
        try {
            const params = new URLSearchParams({ keyword: q, page: 1, page_size: 20 });
            const data = await apiGet(`/api/tasks/all?${params}&status=all`);
            let html = "";
            if (data.tasks?.length) {
                html += '<div class="search-section">📋 任务</div>';
                html += data.tasks.slice(0,5).map(t =>
                    `<div class="search-item" onclick="switchTab('tasks');closeSearch()">${escapeHtml(t.task_name)} <span class="badge badge-${badgeClass(t.status)}">${t.status}</span></div>`
                ).join("");
            }
            if (!html) html = '<div class="search-empty">无结果</div>';
            searchDropdown.innerHTML = html;
            searchDropdown.style.display = "block";
        } catch {}
    }, 300);
});

searchInput?.addEventListener("blur", () => setTimeout(() => { searchDropdown.style.display = "none"; }, 200));

function closeSearch() { searchDropdown.style.display = "none"; searchInput.value = ""; searchInput.blur(); }

function switchTab(name) {
    document.querySelectorAll(".tab").forEach(t => { if (t.dataset.tab === name) t.click(); });
}

// ============================================================
// 点击弹窗外关闭
// ============================================================

document.getElementById("modal-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") closeModal();
});

// ============================================================
// AI 对话悬浮窗 + 配置管理
// ============================================================

const aiFab = document.getElementById("ai-fab");
const aiPanel = document.getElementById("ai-panel");
const aiClose = document.getElementById("ai-close");
const aiClear = document.getElementById("ai-clear");
const aiInput = document.getElementById("ai-input");
const aiSend = document.getElementById("ai-send");
const aiMessages = document.getElementById("ai-messages");
const aiSettingsBtn = document.getElementById("ai-settings-btn");
const aiSettingsPanel = document.getElementById("ai-settings");

let aiPanelOpen = false;
let aiSettingsOpen = false;

function toggleAiPanel() {
    aiPanelOpen = !aiPanelOpen;
    aiPanel.style.display = aiPanelOpen ? "flex" : "none";
    if (aiPanelOpen) {
        loadAiConfig();
        aiInput?.focus();
    }
}

aiFab?.addEventListener("click", toggleAiPanel);
aiClose?.addEventListener("click", toggleAiPanel);

aiSettingsBtn?.addEventListener("click", () => {
    aiSettingsOpen = !aiSettingsOpen;
    aiSettingsPanel.style.display = aiSettingsOpen ? "block" : "none";
    if (aiSettingsOpen) loadAiConfig();
});

aiClear?.addEventListener("click", async () => {
    aiMessages.innerHTML = '<div class="ai-msg ai-msg-system">对话历史已清除。</div>';
    try { await apiPost("/api/chat/clear", { message: "", conversation_id: "default" }); } catch {}
});

// Key 显示/隐藏
document.getElementById("ai-toggle-key")?.addEventListener("click", () => {
    const inp = document.getElementById("ai-api-key");
    inp.type = inp.type === "password" ? "text" : "password";
});

// Enter 发送, Shift+Enter 换行
aiInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendAiMessage();
    }
});

aiSend?.addEventListener("click", sendAiMessage);

// ---- 加载配置 ----
async function loadAiConfig() {
    try {
        // 并行加载配置、模型列表
        const [configRes, modelsRes] = await Promise.all([
            apiGet("/api/chat/config"),
            apiGet("/api/chat/models"),
        ]);

        // 填充 API 地址
        document.getElementById("ai-api-base").value = configRes.config?.api_base || "";

        // 填充模型下拉
        const modelSel = document.getElementById("ai-model-select");
        if (modelsRes.models) {
            modelSel.innerHTML = modelsRes.models.map(m =>
                `<option value="${m.id}">${m.name}</option>`
            ).join("") + '<option value="custom">自定义...</option>';
            const curModel = configRes.config?.model || "";
            const matchModel = modelsRes.models.find(m => m.id === curModel);
            if (matchModel) {
                modelSel.value = curModel;
                document.getElementById("ai-custom-model").value = "";
                document.getElementById("ai-custom-model-group").style.display = "none";
            } else {
                modelSel.value = "custom";
                document.getElementById("ai-custom-model").value = curModel;
                document.getElementById("ai-custom-model-group").style.display = "block";
            }
        }

        // Key
        const keyInp = document.getElementById("ai-api-key");
        keyInp.placeholder = configRes.config?.api_key_set ? `已配置 (${configRes.config.api_key_masked})` : "输入 API Key";
        keyInp.value = ""; // 不回显，只有新输入才更新

    } catch (e) {
        console.error("加载 AI 配置失败:", e);
    }
}

// 模型切换
document.getElementById("ai-model-select")?.addEventListener("change", (e) => {
    const v = e.target.value;
    document.getElementById("ai-custom-model-group").style.display = v === "custom" ? "block" : "none";
    if (v !== "custom") document.getElementById("ai-custom-model").value = "";
});

// ---- 保存配置 ----
document.getElementById("ai-save-btn")?.addEventListener("click", async () => {
    const apiBase = document.getElementById("ai-api-base").value.trim();
    const apiKey = document.getElementById("ai-api-key").value.trim();
    const modelSel = document.getElementById("ai-model-select").value;
    const customModel = document.getElementById("ai-custom-model").value.trim();

    const body = {
        api_base: apiBase,
        api_key: apiKey,
        model: modelSel === "custom" ? customModel : modelSel,
    };

    if (!body.api_base) return toast("请填写 API 地址", "error");
    if (!apiKey && !document.getElementById("ai-api-key").placeholder.startsWith("已配置"))
        return toast("请填写 API Key", "error");
    if (!body.model) return toast("请选择或填写模型", "error");

    try {
        const res = await apiPost("/api/chat/config", body);
        if (res.status === "success") {
            toast("✅ AI 配置已保存", "success");
            // 更新 placeholder
            document.getElementById("ai-api-key").placeholder = `已配置 (${res.config?.api_key_masked || "***"})`;
            document.getElementById("ai-api-key").value = "";
        } else {
            toast(res.message || "保存失败", "error");
        }
    } catch (e) {
        toast("保存失败: " + e.message, "error");
    }
});

// ---- 测试连接 ----
document.getElementById("ai-test-btn")?.addEventListener("click", async () => {
    const resultEl = document.getElementById("ai-test-result");
    resultEl.style.display = "block";
    resultEl.className = "ai-test-result";
    resultEl.textContent = "⏳ 正在测试连接...";

    const apiBase = document.getElementById("ai-api-base").value.trim();
    const apiKey = document.getElementById("ai-api-key").value.trim();
    const modelSel = document.getElementById("ai-model-select").value;
    const customModel = document.getElementById("ai-custom-model").value.trim();

    const body = {
        api_base: apiBase,
        api_key: apiKey,
        model: modelSel === "custom" ? customModel : modelSel,
    };

    try {
        const res = await apiPost("/api/chat/test", body);
        resultEl.className = `ai-test-result ${res.status === "success" ? "success" : "error"}`;
        resultEl.textContent = res.reply || res.message || "未知结果";
    } catch (e) {
        resultEl.className = "ai-test-result error";
        resultEl.textContent = "❌ 网络错误: " + e.message;
    }
});

// ---- 发送消息 ----
async function sendAiMessage() {
    const msg = aiInput?.value?.trim();
    if (!msg) return;

    // 关闭设置面板
    if (aiSettingsOpen) {
        aiSettingsOpen = false;
        aiSettingsPanel.style.display = "none";
    }

    appendAiMsg("user", msg);
    aiInput.value = "";
    aiInput.style.height = "auto";

    const typingEl = appendAiMsg("typing", "");

    try {
        const res = await apiPost("/api/chat", { message: msg, conversation_id: "default" });
        typingEl.remove();

        if (res.reply) {
            appendAiMsg("assistant", res.reply);
        } else if (res.message) {
            appendAiMsg("error", res.message);
        }
    } catch (e) {
        typingEl.remove();
        appendAiMsg("error", "网络错误，请稍后重试");
    }
}

function appendAiMsg(role, content) {
    const el = document.createElement("div");
    el.className = `ai-msg ai-msg-${role}`;

    if (role === "typing") {
        el.className = "ai-typing";
        el.textContent = "思考中";
    } else if (role === "assistant") {
        el.innerHTML = renderAiMarkdown(content);
    } else {
        el.textContent = content;
    }

    aiMessages?.appendChild(el);
    aiMessages.scrollTop = aiMessages.scrollHeight;
    return el;
}

function renderAiMarkdown(text) {
    if (!text) return "";
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\n/g, "<br>");
    return text;
}

// Ctrl+J 打开 AI 面板
document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "j") {
        e.preventDefault();
        toggleAiPanel();
    }
});
