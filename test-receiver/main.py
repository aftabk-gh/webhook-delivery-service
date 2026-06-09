"""
Test receiver for webhook-delivery-service local development.

Simulates a real webhook consumer with configurable failure modes.
Use this to observe delivery behavior, retries, timeouts, and circuit breaker.
"""

import asyncio
from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Webhook Test Receiver")

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

MAX_LOG_SIZE = 500

received_webhooks: deque[dict[str, Any]] = deque(maxlen=MAX_LOG_SIZE)

config: dict[str, Any] = {
    "status_code": 200,
    "delay_seconds": 0.0,
    "fail_next_n": 0,  # fail this many requests then go back to normal
    "timeout_mode": False,  # never respond — triggers sender timeout
    "fail_count": 0,  # internal counter
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConfigUpdate(BaseModel):
    status_code: int | None = None
    delay_seconds: float | None = None
    fail_next_n: int | None = None
    timeout_mode: bool | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/webhook")
async def receive_webhook(request: Request) -> Response:
    body_bytes = await request.body()

    try:
        body_json = await request.json()
    except Exception:
        body_json = None

    entry: dict[str, Any] = {
        "id": len(received_webhooks) + 1,
        "received_at": datetime.now(UTC).isoformat(),
        "headers": dict(request.headers),
        "body": body_json
        if body_json is not None
        else body_bytes.decode("utf-8", errors="replace"),
        "size_bytes": len(body_bytes),
    }
    received_webhooks.appendleft(entry)

    # timeout mode — hold forever (your sender will timeout at 10s)
    if config["timeout_mode"]:
        await asyncio.sleep(60)
        return Response(status_code=200)

    # delay
    if config["delay_seconds"] > 0:
        await asyncio.sleep(config["delay_seconds"])

    # fail_next_n
    if config["fail_next_n"] > 0:
        config["fail_count"] += 1
        if config["fail_count"] <= config["fail_next_n"]:
            return Response(
                content=f"Simulated failure ({config['fail_count']}/{config['fail_next_n']})",
                status_code=500,
            )
        else:
            # reset after exhausting fail count
            config["fail_next_n"] = 0
            config["fail_count"] = 0

    return Response(status_code=config["status_code"])


@app.get("/webhooks")
async def list_webhooks(limit: int = 50) -> list[dict[str, Any]]:
    return list(received_webhooks)[:limit]


@app.delete("/webhooks")
async def clear_webhooks() -> dict[str, str]:
    received_webhooks.clear()
    return {"status": "cleared"}


@app.get("/config")
async def get_config() -> dict[str, Any]:
    return dict(config)


@app.post("/config")
async def update_config(update: ConfigUpdate) -> dict[str, Any]:
    if update.status_code is not None:
        config["status_code"] = update.status_code
    if update.delay_seconds is not None:
        config["delay_seconds"] = update.delay_seconds
    if update.fail_next_n is not None:
        config["fail_next_n"] = update.fail_next_n
        config["fail_count"] = 0
    if update.timeout_mode is not None:
        config["timeout_mode"] = update.timeout_mode
    return dict(config)


@app.post("/config/reset")
async def reset_config() -> dict[str, Any]:
    config["status_code"] = 200
    config["delay_seconds"] = 0.0
    config["fail_next_n"] = 0
    config["timeout_mode"] = False
    config["fail_count"] = 0
    return dict(config)


# ---------------------------------------------------------------------------
# Simple dashboard UI
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Webhook Test Receiver</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    background: #0d1117;
    color: #e6edf3;
    min-height: 100vh;
  }

  header {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  header h1 {
    font-size: 14px;
    font-weight: 600;
    color: #58a6ff;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #3fb950;
    box-shadow: 0 0 6px #3fb950;
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    height: calc(100vh - 53px);
  }

  .sidebar {
    background: #161b22;
    border-right: 1px solid #30363d;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .section-title {
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #8b949e;
    margin-bottom: 10px;
  }

  .config-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
  }

  .config-row label {
    font-size: 11px;
    color: #8b949e;
  }

  .config-row input {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    padding: 6px 10px;
    font-size: 13px;
    font-family: inherit;
    width: 100%;
  }

  .config-row input:focus {
    outline: none;
    border-color: #58a6ff;
  }

  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .toggle-row label {
    font-size: 11px;
    color: #8b949e;
  }

  .toggle {
    position: relative;
    width: 36px; height: 20px;
  }

  .toggle input { display: none; }

  .slider {
    position: absolute; inset: 0;
    background: #30363d;
    border-radius: 20px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .slider:before {
    content: '';
    position: absolute;
    width: 14px; height: 14px;
    background: white;
    border-radius: 50%;
    top: 3px; left: 3px;
    transition: transform 0.2s;
  }

  .toggle input:checked + .slider { background: #da3633; }
  .toggle input:checked + .slider:before { transform: translateX(16px); }

  .btn {
    width: 100%;
    padding: 8px;
    border: none;
    border-radius: 6px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
    letter-spacing: 0.03em;
    transition: opacity 0.15s;
  }

  .btn:hover { opacity: 0.85; }

  .btn-apply { background: #238636; color: white; margin-bottom: 8px; }
  .btn-reset { background: #21262d; color: #8b949e; border: 1px solid #30363d; margin-bottom: 8px; }
  .btn-clear { background: #21262d; color: #f85149; border: 1px solid #30363d; }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }

  .status-ok { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
  .status-fail { background: rgba(248,81,73,0.15); color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
  .status-delay { background: rgba(210,153,34,0.15); color: #d2a520; border: 1px solid rgba(210,153,34,0.3); }
  .status-timeout { background: rgba(188,140,255,0.15); color: #bc8cff; border: 1px solid rgba(188,140,255,0.3); }

  .main {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .toolbar {
    padding: 12px 20px;
    border-bottom: 1px solid #30363d;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .count-badge {
    font-size: 12px;
    color: #8b949e;
  }

  .count-badge span {
    color: #58a6ff;
    font-weight: 700;
  }

  .webhook-list {
    overflow-y: auto;
    flex: 1;
    padding: 12px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .webhook-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .webhook-card:hover { border-color: #58a6ff; }

  .webhook-card.expanded { border-color: #58a6ff; }

  .card-header {
    display: flex;
    align-items: center;
    padding: 10px 14px;
    gap: 10px;
  }

  .seq { font-size: 11px; color: #8b949e; min-width: 28px; }

  .event-type {
    font-size: 12px;
    font-weight: 600;
    color: #58a6ff;
    flex: 1;
  }

  .event-id {
    font-size: 10px;
    color: #8b949e;
    font-family: inherit;
  }

  .ts {
    font-size: 10px;
    color: #8b949e;
    white-space: nowrap;
  }

  .card-body {
    display: none;
    border-top: 1px solid #30363d;
    padding: 14px;
  }

  .card-body.open { display: block; }

  .tab-bar {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;
  }

  .tab {
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    color: #8b949e;
    border: 1px solid transparent;
  }

  .tab.active {
    color: #e6edf3;
    border-color: #30363d;
    background: #21262d;
  }

  .tab-content { display: none; }
  .tab-content.active { display: block; }

  pre {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 12px;
    font-size: 12px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    color: #e6edf3;
    line-height: 1.6;
    font-family: inherit;
    max-height: 300px;
    overflow-y: auto;
  }

  .header-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .header-table td {
    padding: 4px 8px;
    border-bottom: 1px solid #21262d;
    vertical-align: top;
  }

  .header-table td:first-child {
    color: #8b949e;
    white-space: nowrap;
    width: 40%;
  }

  .header-table td:last-child {
    color: #e6edf3;
    word-break: break-all;
  }

  .hmac-row td:first-child { color: #3fb950; font-weight: 600; }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 8px;
    color: #8b949e;
  }

  .empty-state .icon { font-size: 32px; }
  .empty-state p { font-size: 12px; }

  .auto-refresh-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #8b949e;
    cursor: pointer;
  }
</style>
</head>
<body>

<header>
  <div class="dot"></div>
  <h1>Webhook Test Receiver</h1>
</header>

<div class="layout">
  <div class="sidebar">

    <div>
      <div class="section-title">Current Mode</div>
      <div id="mode-display">—</div>
    </div>

    <div>
      <div class="section-title">Configure Behavior</div>

      <div class="config-row">
        <label>Response Status Code</label>
        <input type="number" id="status_code" value="200" min="100" max="599">
      </div>

      <div class="config-row">
        <label>Response Delay (seconds)</label>
        <input type="number" id="delay_seconds" value="0" min="0" step="0.5">
      </div>

      <div class="config-row">
        <label>Fail Next N Requests (then recover)</label>
        <input type="number" id="fail_next_n" value="0" min="0">
      </div>

      <div class="toggle-row">
        <label>Timeout Mode (never respond)</label>
        <label class="toggle">
          <input type="checkbox" id="timeout_mode">
          <span class="slider"></span>
        </label>
      </div>

      <button class="btn btn-apply" onclick="applyConfig()">Apply Config</button>
      <button class="btn btn-reset" onclick="resetConfig()">Reset to Default</button>
    </div>

    <div>
      <div class="section-title">Log</div>
      <button class="btn btn-clear" onclick="clearWebhooks()">Clear All Webhooks</button>
    </div>

  </div>

  <div class="main">
    <div class="toolbar">
      <div class="count-badge">Received: <span id="webhook-count">0</span></div>
      <label class="auto-refresh-toggle">
        <input type="checkbox" id="auto-refresh" checked>
        Auto-refresh (2s)
      </label>
    </div>
    <div class="webhook-list" id="webhook-list">
      <div class="empty-state">
        <div class="icon">📭</div>
        <p>No webhooks received yet.</p>
        <p>Send an event from your API to see it here.</p>
      </div>
    </div>
  </div>
</div>

<script>
let autoRefreshInterval = null;

function startAutoRefresh() {
  autoRefreshInterval = setInterval(loadWebhooks, 2000);
}

function stopAutoRefresh() {
  clearInterval(autoRefreshInterval);
}

document.getElementById('auto-refresh').addEventListener('change', function() {
  if (this.checked) startAutoRefresh();
  else stopAutoRefresh();
});

async function loadConfig() {
  const res = await fetch('/config');
  const cfg = await res.json();

  document.getElementById('status_code').value = cfg.status_code;
  document.getElementById('delay_seconds').value = cfg.delay_seconds;
  document.getElementById('fail_next_n').value = cfg.fail_next_n;
  document.getElementById('timeout_mode').checked = cfg.timeout_mode;

  updateModeDisplay(cfg);
}

function updateModeDisplay(cfg) {
  const el = document.getElementById('mode-display');
  let badges = [];

  if (cfg.timeout_mode) {
    badges.push('<span class="status-badge status-timeout">⏱ TIMEOUT MODE</span>');
  } else if (cfg.status_code >= 500) {
    badges.push('<span class="status-badge status-fail">✗ ' + cfg.status_code + '</span>');
  } else if (cfg.status_code >= 400) {
    badges.push('<span class="status-badge status-fail">✗ ' + cfg.status_code + '</span>');
  } else {
    badges.push('<span class="status-badge status-ok">✓ ' + cfg.status_code + '</span>');
  }

  if (cfg.delay_seconds > 0) {
    badges.push('<span class="status-badge status-delay">⏳ ' + cfg.delay_seconds + 's delay</span>');
  }

  if (cfg.fail_next_n > 0) {
    badges.push('<span class="status-badge status-fail">✗ fail next ' + cfg.fail_next_n + ' (' + cfg.fail_count + ' done)</span>');
  }

  el.innerHTML = '<div style="display:flex;flex-direction:column;gap:6px;">' + badges.join('') + '</div>';
}

async function applyConfig() {
  const payload = {
    status_code: parseInt(document.getElementById('status_code').value),
    delay_seconds: parseFloat(document.getElementById('delay_seconds').value),
    fail_next_n: parseInt(document.getElementById('fail_next_n').value),
    timeout_mode: document.getElementById('timeout_mode').checked,
  };
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const cfg = await res.json();
  updateModeDisplay(cfg);
}

async function resetConfig() {
  const res = await fetch('/config/reset', { method: 'POST' });
  const cfg = await res.json();
  document.getElementById('status_code').value = cfg.status_code;
  document.getElementById('delay_seconds').value = cfg.delay_seconds;
  document.getElementById('fail_next_n').value = cfg.fail_next_n;
  document.getElementById('timeout_mode').checked = cfg.timeout_mode;
  updateModeDisplay(cfg);
}

async function clearWebhooks() {
  await fetch('/webhooks', { method: 'DELETE' });
  document.getElementById('webhook-list').innerHTML = `
    <div class="empty-state">
      <div class="icon">📭</div>
      <p>No webhooks received yet.</p>
    </div>`;
  document.getElementById('webhook-count').textContent = '0';
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function getEventType(webhook) {
  const headers = webhook.headers || {};
  return headers['x-webhook-event-type'] || headers['X-Webhook-Event-Type'] || '(unknown)';
}

function getEventId(webhook) {
  const headers = webhook.headers || {};
  const val = headers['x-webhook-event-id'] || headers['X-Webhook-Event-Id'] || '';
  return val ? val.substring(0, 8) + '…' : '';
}

function getSignature(webhook) {
  const headers = webhook.headers || {};
  return headers['x-webhook-signature'] || headers['X-Webhook-Signature'] || null;
}

function toggleCard(id) {
  const card = document.getElementById('card-' + id);
  const body = card.querySelector('.card-body');
  card.classList.toggle('expanded');
  body.classList.toggle('open');
}

function switchTab(webhookId, tab) {
  const card = document.getElementById('card-' + webhookId);
  card.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  card.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  card.querySelector('[data-tab="' + tab + '"]').classList.add('active');
  card.querySelector('[data-content="' + tab + '"]').classList.add('active');
}

function renderWebhooks(webhooks) {
  const list = document.getElementById('webhook-list');
  document.getElementById('webhook-count').textContent = webhooks.length;

  if (webhooks.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="icon">📭</div>
        <p>No webhooks received yet.</p>
        <p>Send an event from your API to see it here.</p>
      </div>`;
    return;
  }

  list.innerHTML = webhooks.map(wh => {
    const eventType = getEventType(wh);
    const eventId = getEventId(wh);
    const sig = getSignature(wh);

    const headersHtml = Object.entries(wh.headers || {}).map(([k, v]) => {
      const isHmac = k.toLowerCase() === 'x-webhook-signature';
      return `<tr class="${isHmac ? 'hmac-row' : ''}"><td>${k}</td><td>${v}</td></tr>`;
    }).join('');

    const bodyStr = typeof wh.body === 'object'
      ? JSON.stringify(wh.body, null, 2)
      : String(wh.body);

    return `
      <div class="webhook-card" id="card-${wh.id}" onclick="toggleCard(${wh.id})">
        <div class="card-header">
          <span class="seq">#${wh.id}</span>
          <span class="event-type">${eventType}</span>
          ${eventId ? `<span class="event-id">${eventId}</span>` : ''}
          ${sig ? `<span class="status-badge status-ok" style="font-size:10px;">✓ HMAC</span>` : ''}
          <span class="ts">${formatTime(wh.received_at)}</span>
        </div>
        <div class="card-body">
          <div class="tab-bar" onclick="event.stopPropagation()">
            <div class="tab active" data-tab="payload" onclick="switchTab(${wh.id}, 'payload')">Payload</div>
            <div class="tab" data-tab="headers" onclick="switchTab(${wh.id}, 'headers')">Headers</div>
          </div>
          <div class="tab-content active" data-content="payload">
            <pre>${bodyStr}</pre>
          </div>
          <div class="tab-content" data-content="headers" onclick="event.stopPropagation()">
            <table class="header-table"><tbody>${headersHtml}</tbody></table>
          </div>
        </div>
      </div>`;
  }).join('');
}

async function loadWebhooks() {
  const res = await fetch('/webhooks?limit=100');
  const data = await res.json();
  renderWebhooks(data);
  // refresh config mode display too
  const cfgRes = await fetch('/config');
  const cfg = await cfgRes.json();
  updateModeDisplay(cfg);
}

// init
loadConfig();
loadWebhooks();
startAutoRefresh();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)
