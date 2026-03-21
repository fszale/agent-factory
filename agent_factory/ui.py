INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agent-factory</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: #fffaf3;
      --ink: #182028;
      --muted: #6a7178;
      --accent: #c55c2b;
      --accent-dark: #8f3f18;
      --line: #ddd2c4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Iowan Old Style", serif;
      background: radial-gradient(circle at top left, #fff8ee, var(--bg) 50%);
      color: var(--ink);
    }
    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: 100vh;
    }
    .sidebar, .main {
      padding: 24px;
    }
    .sidebar {
      border-right: 1px solid var(--line);
      background: rgba(255, 250, 243, 0.9);
    }
    .brand {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      font-size: 28px;
      margin: 0 0 8px;
    }
    .brand a {
      font-size: 14px;
      color: var(--accent-dark);
      text-decoration: none;
    }
    .subtle {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.4;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      margin-top: 16px;
    }
    .thread-list button, .toolbar button, form button {
      width: 100%;
      margin-top: 8px;
    }
    button {
      border: none;
      background: var(--accent);
      color: white;
      padding: 12px 14px;
      border-radius: 12px;
      cursor: pointer;
      font-weight: 600;
    }
    button.secondary {
      background: #e7d9ca;
      color: var(--ink);
    }
    select, textarea, input {
      width: 100%;
      margin-top: 8px;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: white;
      color: var(--ink);
      font: inherit;
    }
    .messages {
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-height: 60vh;
    }
    .message {
      max-width: 80%;
      padding: 14px 16px;
      border-radius: 16px;
      white-space: pre-wrap;
      line-height: 1.5;
    }
    .message.user {
      align-self: flex-end;
      background: linear-gradient(135deg, var(--accent), var(--accent-dark));
      color: white;
    }
    .message.assistant {
      align-self: flex-start;
      background: #fff;
      border: 1px solid var(--line);
    }
    .meta {
      font-size: 12px;
      color: var(--muted);
      margin-top: 6px;
    }
    .toolbar {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { border-right: none; border-bottom: 1px solid var(--line); }
      .message { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <span>agent-factory</span>
        <a href="/admin">Admin</a>
      </div>
      <div class="subtle">Threaded chat and agent operations surface for installed twins.</div>
      <div class="panel">
        <label for="tokenInput">Bearer Token or API Key</label>
        <input id="tokenInput" type="password" placeholder="Paste a token to call protected APIs" />
        <button class="secondary" id="saveTokenBtn">Save Token</button>
      </div>
      <div class="panel">
        <label for="twinSelect">Twin</label>
        <select id="twinSelect"></select>
        <button id="newThreadBtn">New Thread</button>
      </div>
      <div class="panel">
        <div class="subtle">Threads</div>
        <div id="threadList" class="thread-list"></div>
      </div>
      <div class="panel">
        <div class="subtle">Agent operations</div>
        <button class="secondary" id="refreshTasksBtn">Refresh Tasks</button>
        <div id="taskSummary" class="meta"></div>
      </div>
    </aside>
    <main class="main">
      <div class="toolbar">
        <button class="secondary" id="capabilitiesBtn">Show Capabilities</button>
        <button class="secondary" id="newTaskBtn">Create Agent Task</button>
      </div>
      <div id="messages" class="messages panel"></div>
      <form id="composer" class="panel">
        <label for="messageInput">Message</label>
        <textarea id="messageInput" rows="5" placeholder="Ask the twin something useful."></textarea>
        <button type="submit">Send</button>
      </form>
    </main>
  </div>

  <script>
    const state = {
      twins: [],
      currentTwinId: null,
      currentThreadId: null,
      token: localStorage.getItem("agentFactoryToken") || "",
    };

    const twinSelect = document.getElementById("twinSelect");
    const threadList = document.getElementById("threadList");
    const messages = document.getElementById("messages");
    const messageInput = document.getElementById("messageInput");
    const taskSummary = document.getElementById("taskSummary");
    const tokenInput = document.getElementById("tokenInput");
    tokenInput.value = state.token;

    async function fetchJson(path, options = {}) {
      const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
      if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
      }
      const response = await fetch(path, { ...options, headers });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || response.statusText);
      }
      return response.json();
    }

    function renderMessages(items) {
      messages.innerHTML = "";
      if (!items.length) {
        messages.innerHTML = '<div class="subtle">No messages yet.</div>';
        return;
      }
      for (const item of items) {
        const div = document.createElement("div");
        div.className = `message ${item.role}`;
        div.textContent = item.content;
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = `${item.role} · ${new Date(item.created_at).toLocaleString()}`;
        div.appendChild(meta);
        messages.appendChild(div);
      }
    }

    async function loadTwins() {
      state.twins = await fetchJson("/twins");
      twinSelect.innerHTML = "";
      for (const twin of state.twins) {
        const option = document.createElement("option");
        option.value = twin.twin_id;
        option.textContent = twin.name;
        twinSelect.appendChild(option);
      }
      if (state.twins.length && !state.currentTwinId) {
        state.currentTwinId = state.twins[0].twin_id;
        twinSelect.value = state.currentTwinId;
      }
      await loadThreads();
      await refreshTaskSummary();
    }

    async function loadThreads() {
      if (!state.currentTwinId) return;
      const items = await fetchJson(`/threads?twin_id=${encodeURIComponent(state.currentTwinId)}`);
      threadList.innerHTML = "";
      for (const item of items) {
        const button = document.createElement("button");
        button.className = "secondary";
        button.textContent = item.title;
        button.onclick = async () => {
          state.currentThreadId = item.id;
          await loadMessages();
        };
        threadList.appendChild(button);
      }
      if (items.length && !state.currentThreadId) {
        state.currentThreadId = items[0].id;
        await loadMessages();
      }
      if (!items.length) {
        state.currentThreadId = null;
        renderMessages([]);
      }
    }

    async function loadMessages() {
      if (!state.currentThreadId) {
        renderMessages([]);
        return;
      }
      const items = await fetchJson(`/threads/${state.currentThreadId}/messages`);
      renderMessages(items);
    }

    async function createThread() {
      const payload = await fetchJson("/threads", {
        method: "POST",
        body: JSON.stringify({ twin_id: state.currentTwinId, title: `${state.currentTwinId} thread` }),
      });
      state.currentThreadId = payload.id;
      await loadThreads();
      await loadMessages();
    }

    async function sendMessage(event) {
      event.preventDefault();
      if (!state.currentThreadId) {
        await createThread();
      }
      const content = messageInput.value.trim();
      if (!content) return;
      messageInput.value = "";
      await fetchJson(`/threads/${state.currentThreadId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message: content }),
      });
      await loadMessages();
      await refreshTaskSummary();
    }

    async function showCapabilities() {
      if (!state.currentTwinId) return;
      const payload = await fetchJson(`/twins/${state.currentTwinId}/capabilities`);
      alert(JSON.stringify(payload, null, 2));
    }

    async function createTask() {
      if (!state.currentTwinId) return;
      const prompt = window.prompt("Task instruction");
      if (!prompt) return;
      await fetchJson("/tasks", {
        method: "POST",
        body: JSON.stringify({
          twin_id: state.currentTwinId,
          task_type: "agent_instruction",
          input_payload: { instruction: prompt },
          thread_id: state.currentThreadId,
        }),
      });
      await refreshTaskSummary();
    }

    async function refreshTaskSummary() {
      if (!state.currentTwinId) return;
      const tasks = await fetchJson(`/tasks?twin_id=${encodeURIComponent(state.currentTwinId)}`);
      taskSummary.textContent = `${tasks.length} tasks recorded`;
    }

    function saveToken() {
      state.token = tokenInput.value.trim();
      localStorage.setItem("agentFactoryToken", state.token);
      loadTwins().catch((error) => {
        messages.innerHTML = `<div class="message assistant">Failed to load app: ${error.message}</div>`;
      });
    }

    twinSelect.addEventListener("change", async (event) => {
      state.currentTwinId = event.target.value;
      state.currentThreadId = null;
      await loadThreads();
      await refreshTaskSummary();
    });

    document.getElementById("composer").addEventListener("submit", sendMessage);
    document.getElementById("newThreadBtn").addEventListener("click", createThread);
    document.getElementById("capabilitiesBtn").addEventListener("click", showCapabilities);
    document.getElementById("newTaskBtn").addEventListener("click", createTask);
    document.getElementById("refreshTasksBtn").addEventListener("click", refreshTaskSummary);
    document.getElementById("saveTokenBtn").addEventListener("click", saveToken);

    loadTwins().catch((error) => {
      messages.innerHTML = `<div class="message assistant">Failed to load app: ${error.message}</div>`;
    });
  </script>
</body>
</html>
"""


ADMIN_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agent-factory admin</title>
  <style>
    :root {
      --bg: #171f28;
      --panel: #202a36;
      --ink: #edf2f7;
      --muted: #99a7b8;
      --accent: #d6683c;
      --line: #324253;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Avenir Next", sans-serif;
      background: linear-gradient(180deg, #121820, var(--bg));
      color: var(--ink);
    }
    .page { padding: 24px; max-width: 1300px; margin: 0 auto; }
    h1, h2 { margin: 0 0 12px; }
    .subtle { color: var(--muted); font-size: 14px; line-height: 1.5; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 16px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      min-height: 160px;
    }
    input, textarea, select, button {
      width: 100%;
      margin-top: 8px;
      border-radius: 10px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
    }
    input, textarea, select { background: #10161d; color: var(--ink); }
    button {
      border: none;
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 600;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
    }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>agent-factory admin</h1>
    <div class="subtle">Govern approvals, corrections, artifact proposals, client credentials, and audit trails.</div>

    <div class="panel">
      <label for="adminToken">Admin Bearer Token</label>
      <input id="adminToken" type="password" placeholder="Paste a Supabase bearer token for an approved admin user" />
      <button id="saveAdminToken">Save Admin Token</button>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Overview</h2>
        <button id="refreshOverview">Refresh</button>
        <pre id="overviewOutput"></pre>
      </section>
      <section class="panel">
        <h2>Create API Client</h2>
        <input id="clientId" placeholder="client_id" />
        <input id="clientName" placeholder="client display name" />
        <input id="clientFactoryId" placeholder="factory_id (optional)" />
        <textarea id="clientScopes" rows="3" placeholder="scopes, comma separated"></textarea>
        <textarea id="clientTwins" rows="2" placeholder="allowed twins, comma separated or *"></textarea>
        <button id="createClientBtn">Create Client</button>
        <pre id="clientCreateOutput"></pre>
      </section>
      <section class="panel">
        <h2>Approvals</h2>
        <button id="refreshApprovals">Refresh</button>
        <pre id="approvalsOutput"></pre>
      </section>
      <section class="panel">
        <h2>Corrections</h2>
        <button id="refreshCorrections">Refresh</button>
        <pre id="correctionsOutput"></pre>
      </section>
      <section class="panel">
        <h2>Artifacts</h2>
        <button id="refreshArtifacts">Refresh</button>
        <pre id="artifactsOutput"></pre>
      </section>
      <section class="panel">
        <h2>Audit Log</h2>
        <button id="refreshAudit">Refresh</button>
        <pre id="auditOutput"></pre>
      </section>
    </div>
  </div>

  <script>
    const state = { token: localStorage.getItem("agentFactoryAdminToken") || "" };
    const adminToken = document.getElementById("adminToken");
    adminToken.value = state.token;

    async function fetchJson(path, options = {}) {
      const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
      if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
      }
      const response = await fetch(path, { ...options, headers });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || response.statusText);
      }
      return response.json();
    }

    function render(id, payload) {
      document.getElementById(id).textContent = JSON.stringify(payload, null, 2);
    }

    function parseList(text, fallback = ["*"]) {
      const items = text.split(",").map((item) => item.trim()).filter(Boolean);
      return items.length ? items : fallback;
    }

    async function refreshOverview() {
      render("overviewOutput", await fetchJson("/admin/overview"));
    }

    async function refreshApprovals() {
      render("approvalsOutput", await fetchJson("/approvals"));
    }

    async function refreshCorrections() {
      render("correctionsOutput", await fetchJson("/corrections"));
    }

    async function refreshArtifacts() {
      render("artifactsOutput", await fetchJson("/artifacts"));
    }

    async function refreshAudit() {
      render("auditOutput", await fetchJson("/audit"));
    }

    async function createClient() {
      const payload = await fetchJson("/api-clients", {
        method: "POST",
        body: JSON.stringify({
          client_id: document.getElementById("clientId").value.trim(),
          name: document.getElementById("clientName").value.trim(),
          factory_id: document.getElementById("clientFactoryId").value.trim() || null,
          allowed_actions: parseList(document.getElementById("clientScopes").value, []),
          allowed_twins: parseList(document.getElementById("clientTwins").value, ["*"]),
        }),
      });
      render("clientCreateOutput", payload);
    }

    function saveToken() {
      state.token = adminToken.value.trim();
      localStorage.setItem("agentFactoryAdminToken", state.token);
    }

    document.getElementById("saveAdminToken").addEventListener("click", saveToken);
    document.getElementById("refreshOverview").addEventListener("click", refreshOverview);
    document.getElementById("refreshApprovals").addEventListener("click", refreshApprovals);
    document.getElementById("refreshCorrections").addEventListener("click", refreshCorrections);
    document.getElementById("refreshArtifacts").addEventListener("click", refreshArtifacts);
    document.getElementById("refreshAudit").addEventListener("click", refreshAudit);
    document.getElementById("createClientBtn").addEventListener("click", createClient);
  </script>
</body>
</html>
"""
