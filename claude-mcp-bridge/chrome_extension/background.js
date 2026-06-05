const WS_URL = "ws://localhost:9001";
const RECONNECT_DELAY_MS = 3000;

let socket = null;
let attachedTabs = new Set();
let buffer = [];
let isConnecting = false;
let eventCount = 0;
let errorCount = 0;
let recentErrors = [];

const requestUrlMap = new Map();

function isLocalTraffic(url) {
  if (!url) return false;
  return url.includes('localhost') || url.includes('127.0.0.1') || url.includes('0.0.0.0');
}

function connectWS() {
  if (isConnecting || (socket && socket.readyState === WebSocket.OPEN)) return;
  isConnecting = true;
  socket = new WebSocket(WS_URL);
  socket.onopen = () => {
    isConnecting = false;
    console.log("[MCP Bridge] Connected");
    buffer.forEach(e => socket.send(JSON.stringify(e)));
    buffer = [];
  };
  socket.onclose = () => {
    isConnecting = false;
    setTimeout(connectWS, RECONNECT_DELAY_MS);
  };
  socket.onerror = () => { isConnecting = false; };
}

function send(event) {
  eventCount++;
  if (event.type === "console_error" || event.type === "page_error") {
    errorCount++;
    recentErrors.unshift(event);
    if (recentErrors.length > 10) recentErrors.pop();
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(event));
  } else {
    buffer.push(event);
    connectWS();
  }
}

async function attachDebugger(tabId) {
  if (attachedTabs.has(tabId)) return;
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
    await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
    await chrome.debugger.sendCommand({ tabId }, "Log.enable");
    await chrome.debugger.sendCommand({ tabId }, "Network.enable");
    attachedTabs.add(tabId);
  } catch (e) {}
}

async function detachDebugger(tabId) {
  if (!attachedTabs.has(tabId)) return;
  try { await chrome.debugger.detach({ tabId }); } catch (_) {}
  attachedTabs.delete(tabId);
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  const tabId = source.tabId;
  const ts = new Date().toISOString();

  if (method === "Runtime.consoleAPICalled" && params.type === "error") {
    const text = params.args?.map(a => a.value ?? a.description ?? "").join(" ");
    send({ type: "console_error", tabId, timestamp: ts, message: text,
           stackTrace: params.stackTrace ?? null });
  }
  if (method === "Runtime.exceptionThrown") {
    const ex = params.exceptionDetails;
    send({ type: "page_error", tabId, timestamp: ts, message: ex.text,
           exception: ex.exception?.description ?? null, url: ex.url ?? null,
           lineNumber: ex.lineNumber ?? null, stackTrace: ex.stackTrace ?? null });
  }
  if (method === "Log.entryAdded" && params.entry?.level === "error") {
    send({ type: "console_error", tabId, timestamp: ts,
           message: params.entry.text, url: params.entry.url ?? null,
           lineNumber: params.entry.lineNumber ?? null });
  }
  if (method === "Network.requestWillBeSent") {
    requestUrlMap.set(params.requestId, params.request.url);
  }
  if (method === "Network.loadingFinished") {
    requestUrlMap.delete(params.requestId);
  }
  if (method === "Network.loadingFailed") {
    const eventUrl = params.response?.url || params.request?.url || requestUrlMap.get(params.requestId) || '';
    if (!isLocalTraffic(eventUrl)) return;
    const sourceUrl = requestUrlMap.get(params.requestId) || "";
    socket.send(JSON.stringify({
        type: "request_failed",
        requestId: params.requestId,
        errorText: params.errorText,
        url: sourceUrl
    }));
    requestUrlMap.delete(params.requestId);
  }
  if (method === "Network.responseReceived" && params.response?.status >= 400) {
    const eventUrl = params.response?.url || params.request?.url || requestUrlMap.get(params.requestId) || '';
    if (!isLocalTraffic(eventUrl)) return;
    send({ type: "request_failed", tabId, timestamp: ts,
           url: params.response.url, status: params.response.status });
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "getStatus") {
    sendResponse({
      connected: socket?.readyState === WebSocket.OPEN,
      eventCount, errorCount,
      tabCount: attachedTabs.size,
      recentErrors: recentErrors.slice(0, 5)
    });
  }
  if (msg.action === "clearBuffer") {
    eventCount = 0; errorCount = 0; recentErrors = [];
  }
});

chrome.tabs.onActivated.addListener(({ tabId }) => attachDebugger(tabId));
chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading") attachDebugger(tabId);
});
chrome.tabs.onRemoved.addListener((tabId) => detachDebugger(tabId));

connectWS();
chrome.tabs.query({}, (tabs) => {
  tabs.forEach(t => { if (t.id) attachDebugger(t.id); });
});
