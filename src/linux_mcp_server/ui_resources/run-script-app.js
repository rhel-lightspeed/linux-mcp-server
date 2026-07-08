export {};

const DEFAULT_REQUEST_TIMEOUT_MSEC = 60000;
const PREVIEW_LINES = 5;

// ---- MCP Host Protocol ----
// JSON-RPC 2.0 over postMessage for communicating with the MCP host.

let nextId = 1;
const pendingRequests = new Map();
let hostCallbacks = {};

function sendRequest(method, params, opts) {
  const id = nextId++;
  window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
  return new Promise((resolve, reject) => {
    const timeout = opts?.timeout ?? DEFAULT_REQUEST_TIMEOUT_MSEC;
    const timer = setTimeout(() => {
      pendingRequests.delete(id);
      reject(new Error(`Request '${method}' timed out`));
    }, timeout);
    pendingRequests.set(id, { resolve, reject, timer });
  });
}

function sendNotification(method, params) {
  window.parent.postMessage({ jsonrpc: "2.0", method, params }, "*");
}

window.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || data.jsonrpc !== "2.0") return;

  // Response to a request we sent
  if ("id" in data && !("method" in data)) {
    const pending = pendingRequests.get(data.id);
    if (!pending) return;
    pendingRequests.delete(data.id);
    if (pending.timer) clearTimeout(pending.timer);
    if (data.error) {
      pending.reject(new Error(data.error.message));
    } else {
      pending.resolve(data.result);
    }
    return;
  }

  // Request from host (needs a response)
  if ("id" in data && "method" in data) {
    if (data.method === "ui/resource-teardown") {
      hostCallbacks.onTeardown?.();
      window.parent.postMessage({ jsonrpc: "2.0", id: data.id, result: {} }, "*");
    }
    return;
  }

  // Notification from host
  if ("method" in data && !("id" in data)) {
    switch (data.method) {
      case "ui/notifications/tool-input":
        hostCallbacks.onToolInput?.(data.params);
        break;
      case "ui/notifications/tool-result":
        hostCallbacks.onToolResult?.(data.params);
        break;
      case "ui/notifications/host-context-changed":
        hostCallbacks.onHostContextChanged?.(data.params);
        break;
    }
  }
});

function callServerTool(name, args, opts) {
  return sendRequest("tools/call", { name, arguments: args }, opts);
}

function sendMessage(role, content) {
  return sendRequest("ui/message", { role, content });
}

// Adapted from @modelcontextprotocol/ext-apps (Apache-2.0 / MIT)
// https://github.com/modelcontextprotocol/ext-apps
function setupSizeChangedNotifications() {
  let scheduled = false;
  let lastWidth = 0;
  let lastHeight = 0;

  const sendBodySizeChanged = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      const html = document.documentElement;

      // Measure content height via max-content to avoid clamping to viewport.
      // Width uses window.innerWidth to avoid a reflow that destroys scroll
      // positions in horizontal scroll containers.
      const originalHeight = html.style.height;
      html.style.height = "max-content";
      const height = Math.ceil(html.getBoundingClientRect().height);
      html.style.height = originalHeight;

      const width = Math.ceil(window.innerWidth);

      if (width !== lastWidth || height !== lastHeight) {
        lastWidth = width;
        lastHeight = height;
        sendNotification("ui/notifications/size-changed", { width, height });
      }
    });
  };

  sendBodySizeChanged();

  const resizeObserver = new ResizeObserver(sendBodySizeChanged);
  resizeObserver.observe(document.documentElement);
  resizeObserver.observe(document.body);
}

// ---- Theming ----

function applyTheme(hostContext) {
  const el = document.documentElement;

  if (hostContext.theme) {
    el.setAttribute("data-theme", hostContext.theme);
    el.style.colorScheme = hostContext.theme;
  }

  if (hostContext.styles?.variables) {
    for (const [key, value] of Object.entries(hostContext.styles.variables)) {
      el.style.setProperty(key, value);
    }
  }

  if (hostContext.styles?.css?.fonts) {
    let styleEl = document.getElementById("host-fonts");
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "host-fonts";
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = hostContext.styles.css.fonts;
  }
}

// ---- DOM references ----

const $ = (id) => document.getElementById(id);

const els = {
  connecting: $("connecting"),
  error: $("error"),
  errorMessage: $("error-message"),
  placeholder: $("placeholder"),
  app: $("app"),
  hostName: $("host-name"),
  description: $("description"),
  languageLabel: $("language-label"),
  scriptContent: $("script-content"),
  showMoreContainer: $("show-more-container"),
  showMoreLink: $("show-more-link"),
  actionButtons: $("action-buttons"),
  btnAllow: $("btn-allow"),
  btnDeny: $("btn-deny"),
  statusAllowed: $("status-allowed"),
  statusRejected: $("status-rejected"),
  executionState: $("execution-state"),
};

// ---- App state ----

// phase: "connecting" | "error" | "waiting-for-data" | "ready"
const state = {
  phase: "connecting",
  errorMessage: null,
  executionState: "initial",
  toolParams: null,
  toolResult: null,
  executionTimeout: DEFAULT_REQUEST_TIMEOUT_MSEC,
  showFullScript: false,
};

// ---- Rendering ----

function formatExecutionState(s) {
  switch (s) {
    case "waiting-approval":
      return "Waiting Approval";
    case "success":
    case "failure":
      return "Executed";
    case "rejected-gatekeeper":
      return "Gatekeeper Rejected";
    case "rejected-user":
      return "User Rejected";
    case "executing":
      return "Executing";
    case "initial":
      return "Initial";
  }
}

function renderScript() {
  const script = state.toolParams.script.trim();
  const lines = script.split("\n");
  const hasMore = lines.length > PREVIEW_LINES;

  if (state.showFullScript || !hasMore) {
    els.scriptContent.textContent = script;
  } else {
    els.scriptContent.textContent = lines.slice(0, PREVIEW_LINES).join("\n") + "\n...";
  }

  if (hasMore) {
    els.showMoreContainer.hidden = false;
    const hiddenCount = lines.length - PREVIEW_LINES;
    els.showMoreLink.textContent = state.showFullScript ? "Show less" : `Show all (${hiddenCount} more lines)`;
  } else {
    els.showMoreContainer.hidden = true;
  }
}

function render() {
  // Top-level phase visibility
  els.connecting.hidden = state.phase !== "connecting";
  els.error.hidden = state.phase !== "error";
  els.placeholder.hidden = state.phase !== "waiting-for-data";
  els.app.hidden = state.phase !== "ready";

  if (state.phase === "error") {
    els.errorMessage.textContent = state.errorMessage;
    return;
  }

  if (state.phase !== "ready") return;

  // App content
  els.hostName.textContent = state.toolParams.host || "localhost";
  els.description.textContent = state.toolParams.description;
  els.languageLabel.textContent = state.toolParams.scriptType;
  renderScript();

  // Action area: buttons vs. status text
  const s = state.executionState;
  const showButtons = s === "initial" || s === "waiting-approval";
  els.actionButtons.hidden = !showButtons;
  els.statusAllowed.hidden = !(s === "success" || s === "failure" || s === "executing");
  els.statusRejected.hidden = !(s === "rejected-user" || s === "rejected-gatekeeper");

  if (showButtons) {
    const enabled = s === "waiting-approval";
    els.btnAllow.disabled = !enabled;
    els.btnDeny.disabled = !enabled;
  }

  if (s === "rejected-user") {
    els.statusRejected.textContent = "Denied";
  } else if (s === "rejected-gatekeeper") {
    els.statusRejected.textContent = "Automatically rejected: " + (state.toolResult?.detail || "");
  }

  els.executionState.textContent = formatExecutionState(s);
}

// ---- App logic ----

function formatOutput(params, result, execResult) {
  const lines = params.script.trim().split("\n");
  let text =
    lines.length > 1
      ? `Script id=${result.id} (${params.description}) executed`
      : `Script \`${params.script}\` executed`;

  if (execResult.state === "success") {
    text += " successfully, ";
  } else {
    text += ", ";
  }

  text += `and returned ${execResult.state}. Output:\n${execResult.output}`;
  return text;
}

function formatOutputForError(params, result, message) {
  const lines = params.script.trim().split("\n");
  return lines.length > 1
    ? `Script id=${result.id} (${params.description}) failed to execute: ${message}`
    : `Script \`${params.script}\` failed to execute: ${message}`;
}

async function handleAccept() {
  if (!state.toolParams || !state.toolResult) return;

  state.executionState = "executing";
  render();

  let outputToModel = "";

  try {
    const result = await callServerTool(
      "execute_script",
      { id: state.toolResult.id },
      { timeout: state.executionTimeout },
    );

    if (result.isError) {
      const text = result.content?.find((c) => c.type === "text")?.text;
      throw new Error(text || "Unknown error");
    }

    const execResult = result.structuredContent;
    state.executionState = execResult.state;

    outputToModel = formatOutput(state.toolParams, state.toolResult, execResult);
  } catch (e) {
    const errorMessage = e instanceof Error ? e.message : String(e);
    outputToModel = formatOutputForError(state.toolParams, state.toolResult, errorMessage);
    state.executionState = "failure";
  }

  render();

  sendMessage("user", [{ type: "text", text: outputToModel }]);
}

async function handleReject() {
  if (!state.toolResult) return;

  state.executionState = "rejected-user";
  render();
  callServerTool("reject_script", { id: state.toolResult.id });
}

function onToolInput(params) {
  const args = params.arguments;
  state.toolParams = {
    script: args.script,
    scriptType: args.script_type,
    description: args.description,
    readonly: args.readonly,
    token: args.token,
    host: args.host,
  };
  tryShowApp();
}

function onToolResult(result) {
  const sc = result.structuredContent;
  if (!sc) return;

  state.toolResult = {
    status: sc.status,
    detail: sc.detail,
    id: sc.id,
  };
  tryShowApp();
}

function tryShowApp() {
  if (!state.toolParams || !state.toolResult) return;

  state.phase = "ready";
  render();

  // Fetch execution details from server
  callServerTool("get_execution_details", { id: state.toolResult.id }).then((result) => {
    if (result.isError) return;
    const sc = result.structuredContent;
    if (sc) {
      state.executionState = sc.state;
      // Add 5 seconds grace period here so the timeout is always coming from
      // the MCP server which contains more structured details
      state.executionTimeout = sc.timeout * 1000 + 5000;
      render();
    }
  });
}

// ---- Event handlers ----

els.btnAllow.addEventListener("click", handleAccept);
els.btnDeny.addEventListener("click", handleReject);
els.showMoreLink.addEventListener("click", () => {
  state.showFullScript = !state.showFullScript;
  renderScript();
});

// ---- Initialize ----

async function init() {
  try {
    const result = await sendRequest("ui/initialize", {
      appInfo: { name: "Run Script App", version: "1.0.0" },
      appCapabilities: {},
      protocolVersion: "2026-01-26",
    });

    hostCallbacks = {
      onToolInput,
      onToolResult,
      onHostContextChanged: (ctx) => applyTheme(ctx),
      onTeardown: () => console.log("[APP] App is being torn down"),
    };

    sendNotification("ui/notifications/initialized");
    setupSizeChangedNotifications();

    applyTheme(result.hostContext || {});

    state.phase = "waiting-for-data";
  } catch (e) {
    state.phase = "error";
    state.errorMessage = e instanceof Error ? e.message : String(e);
  }

  render();
}

init();
