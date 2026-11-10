const API_BASE = "/admin/api";
let password = "";

const treeContainer = document.getElementById("tree-container");
const previewBody = document.getElementById("preview-body");
const previewTitle = document.getElementById("preview-title");
const closePreviewBtn = document.getElementById("close-preview");
const statusText = document.getElementById("status-text");
const divider = document.getElementById("divider");
const mainEl = document.querySelector("main");

function setStatus(text) {
  statusText.textContent = text;
}

function requirePassword() {
  const saved = sessionStorage.getItem("webPassword");
  if (saved) {
    password = saved;
    return true;
  }
  return false;
}

async function apiGet(path, params = {}) {
  const url = new URL(API_BASE + path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const resp = await fetch(url.toString(), {
    headers: { "X-Web-Password": password },
  });
  if (resp.status === 401) {
    throw new Error("密码错误或未提供密码");
  }
  const data = await resp.json();
  if (!data.success) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function formatTime(isoStr) {
  if (!isoStr) return "-";
  // "2025-11-27T16:46:17.811738" -> "2025-11-27 16:46:17"
  return isoStr.replace("T", " ").replace(/\.\d+$/, "");
}

function renderTree(node, container) {
  const div = document.createElement("div");
  div.className = "tree-node";
  div.dataset.path = node.path;
  div.dataset.type = node.type;
  const title = document.createElement("div");
  title.textContent = `${node.name || "/"} (${node.type})`;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${node.size_human || "-"} | 创建: ${formatTime(node.created_time)} | 修改: ${formatTime(node.modified_time)}`;

  div.appendChild(title);
  div.appendChild(meta);

  if (node.type === "file") {
    div.addEventListener("click", () => loadFile(node.path));
  }

  container.appendChild(div);

  if (node.children && node.children.length) {
    const childWrap = document.createElement("div");
    childWrap.className = "child-nodes";
    node.children.forEach((child) => renderTree(child, childWrap));
    container.appendChild(childWrap);
  }
}

async function loadTree(path = "/") {
  setStatus("加载文件树...");
  treeContainer.innerHTML = "";
  try {
    const data = await apiGet("/tree", { path, max_depth: 5 });
    renderTree(data.tree, treeContainer);
    setStatus("已连接");
  } catch (err) {
    setStatus(err.message);
    treeContainer.innerHTML = `<div class="error">${err.message}</div>`;
    if (err.message.includes("密码")) {
      sessionStorage.removeItem("webPassword");
      password = "";
    }
    throw err;
  }
}

function formatCsv(content) {
  const lines = content.trim().split(/\r?\n/);
  const table = document.createElement("table");
  table.style.borderCollapse = "collapse";
  table.style.width = "100%";
  lines.forEach((line) => {
    const row = document.createElement("tr");
    line.split(",").forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell;
      td.style.border = "1px solid #e5e7eb";
      td.style.padding = "4px 6px";
      row.appendChild(td);
    });
    table.appendChild(row);
  });
  return table;
}

function formatMarkdown(text) {
  const safe = text
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // Minimal markdown (headings + bold/italic)
  return safe
    .replace(/^### (.*$)/gim, "<h3>$1</h3>")
    .replace(/^## (.*$)/gim, "<h2>$1</h2>")
    .replace(/^# (.*$)/gim, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/gim, "<em>$1</em>")
    .replace(/\n/g, "<br />");
}

async function loadFile(path) {
  setStatus(`读取 ${path}...`);
  previewTitle.textContent = path;
  try {
    const data = await apiGet("/file", { path });
    const ext = data.extension;
    previewBody.innerHTML = "";

    if (ext === ".csv") {
      previewBody.appendChild(formatCsv(data.content));
    } else if (ext === ".md" || ext === ".markdown") {
      previewBody.innerHTML = formatMarkdown(data.content);
    } else {
      const pre = document.createElement("pre");
      pre.textContent = data.content;
      previewBody.appendChild(pre);
    }

    if (data.truncated) {
      const warn = document.createElement("div");
      warn.className = "meta";
      warn.textContent = "内容已截断，文件较大。";
      previewBody.appendChild(warn);
    }

    setStatus("已连接");
  } catch (err) {
    previewBody.innerHTML = `<div class="error">${err.message}</div>`;
    setStatus(err.message);
  }
}

function setupLogin() {
  const overlay = document.getElementById("login-overlay");
  const input = document.getElementById("password-input");
  const btn = document.getElementById("login-btn");
  const error = document.getElementById("login-error");

  const tryLogin = async () => {
    password = input.value.trim();
    if (!password) {
      error.textContent = "请输入密码";
      return;
    }
    try {
      await loadTree("/");
      sessionStorage.setItem("webPassword", password);
      overlay.style.display = "none";
    } catch (e) {
      error.textContent = e.message;
    }
  };

  btn.addEventListener("click", tryLogin);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") tryLogin();
  });
}

closePreviewBtn.addEventListener("click", () => {
  previewBody.innerHTML = "点击左侧文件进行预览";
  previewTitle.textContent = "预览";
});

function setupResizer() {
  let isDragging = false;
  let isVertical = window.innerWidth <= 900;
  const root = document.documentElement;

  function updateOrientation() {
    isVertical = window.innerWidth <= 900;
    if (isVertical) {
      divider.style.cursor = "row-resize";
    } else {
      divider.style.cursor = "col-resize";
    }
  }

  divider.addEventListener("mousedown", (e) => {
    isDragging = true;
    divider.classList.add("dragging");
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const rect = mainEl.getBoundingClientRect();
    if (!isVertical) {
      const min = 220;
      const max = Math.max(min, rect.width - 240);
      let newWidth = e.clientX - rect.left;
      newWidth = Math.max(min, Math.min(max, newWidth));
      root.style.setProperty("--left-width", `${newWidth}px`);
    } else {
      const minH = 220;
      const maxH = Math.max(minH, rect.height - 260);
      let newHeight = e.clientY - rect.top;
      newHeight = Math.max(minH, Math.min(maxH, newHeight));
      root.style.setProperty("--top-height", `${newHeight}px`);
    }
  });
  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      divider.classList.remove("dragging");
    }
  });
  window.addEventListener("resize", updateOrientation);
  updateOrientation();
}

window.addEventListener("DOMContentLoaded", async () => {
  setupLogin();
  setupResizer();
  if (requirePassword()) {
    try {
      await loadTree("/");
      document.getElementById("login-overlay").style.display = "none";
    } catch {
      // password invalid, show overlay
    }
  }
});
