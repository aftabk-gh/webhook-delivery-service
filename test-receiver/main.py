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

MAX_LOG_SIZE = 500

received_webhooks: deque[dict[str, Any]] = deque(maxlen=MAX_LOG_SIZE)

config: dict[str, Any] = {
    "status_code": 200,
    "delay_seconds": 0.0,
    "fail_next_n": 0,
    "timeout_mode": False,
    "fail_count": 0,
}


class ConfigUpdate(BaseModel):
    status_code: int | None = None
    delay_seconds: float | None = None
    fail_next_n: int | None = None
    timeout_mode: bool | None = None


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

    if config["timeout_mode"]:
        await asyncio.sleep(60)
        return Response(status_code=200)

    if config["delay_seconds"] > 0:
        await asyncio.sleep(config["delay_seconds"])

    if config["fail_next_n"] > 0:
        config["fail_count"] += 1
        if config["fail_count"] <= config["fail_next_n"]:
            return Response(
                content=f"Simulated failure ({config['fail_count']}/{config['fail_next_n']})",
                status_code=500,
            )
        else:
            config["fail_next_n"] = 0
            config["fail_count"] = 0

    return Response(status_code=config["status_code"])


@app.get("/webhooks")
async def list_webhooks(limit: int = 100) -> list[dict[str, Any]]:
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


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Webhook Test Receiver</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🪝</text></svg>">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111827;min-height:100vh;font-size:14px}
a{color:inherit;text-decoration:none}

/* layout */
.topbar{background:#fff;border-bottom:1px solid #e5e7eb;padding:0 24px;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.topbar-left{display:flex;align-items:center;gap:10px}
.logo{font-size:13px;font-weight:600;color:#111827;letter-spacing:-0.01em}
.logo span{color:#6366f1}
.live-dot{width:7px;height:7px;border-radius:50%;background:#10b981;flex-shrink:0}
.live-dot.off{background:#d1d5db}
.topbar-right{display:flex;align-items:center;gap:8px}

.layout{display:grid;grid-template-columns:288px 1fr;height:calc(100vh - 52px)}

/* sidebar */
.sidebar{background:#fff;border-right:1px solid #e5e7eb;overflow-y:auto;padding:20px 16px;display:flex;flex-direction:column;gap:24px}
.section-label{font-size:11px;font-weight:600;color:#6b7280;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:10px}

/* mode pills */
.mode-pills{display:flex;flex-direction:column;gap:6px}
.mode-pill{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-radius:8px;border:1px solid #e5e7eb;background:#f9fafb;cursor:pointer;transition:all 0.15s;user-select:none}
.mode-pill:hover{border-color:#6366f1;background:#f0f0ff}
.mode-pill.active{border-color:#6366f1;background:#eef2ff}
.mode-pill-label{font-size:13px;font-weight:500;color:#374151}
.mode-pill-desc{font-size:11px;color:#9ca3af;margin-top:1px}
.mode-pill-left{display:flex;flex-direction:column}
.pill-check{width:18px;height:18px;border-radius:50%;border:2px solid #d1d5db;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all 0.15s}
.mode-pill.active .pill-check{background:#6366f1;border-color:#6366f1}
.pill-check svg{display:none;width:10px;height:10px}
.mode-pill.active .pill-check svg{display:block}

/* divider */
.divider{height:1px;background:#f3f4f6;margin:0 -16px}

/* form fields */
.field{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
.field label{font-size:12px;font-weight:500;color:#374151}
.field input[type=number]{height:34px;border:1px solid #e5e7eb;border-radius:7px;padding:0 10px;font-size:13px;color:#111827;background:#fff;width:100%;outline:none;font-family:inherit;transition:border-color 0.15s}
.field input[type=number]:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,0.08)}
.field .hint{font-size:11px;color:#9ca3af}

/* toggle */
.toggle-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.toggle-row label{font-size:12px;font-weight:500;color:#374151}
.toggle-row .sub{font-size:11px;color:#9ca3af}
.switch{position:relative;width:36px;height:20px;flex-shrink:0}
.switch input{display:none}
.track{position:absolute;inset:0;background:#e5e7eb;border-radius:20px;cursor:pointer;transition:background 0.2s}
.track:before{content:'';position:absolute;width:14px;height:14px;background:#fff;border-radius:50%;top:3px;left:3px;transition:transform 0.2s;box-shadow:0 1px 3px rgba(0,0,0,0.15)}
.switch input:checked + .track{background:#ef4444}
.switch input:checked + .track:before{transform:translateX(16px)}

/* buttons */
.btn{height:34px;border-radius:7px;border:none;font-family:inherit;font-size:13px;font-weight:500;cursor:pointer;transition:all 0.15s;display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 14px}
.btn-primary{background:#6366f1;color:#fff;width:100%;margin-bottom:6px}
.btn-primary:hover{background:#4f46e5}
.btn-ghost{background:#f3f4f6;color:#374151;width:100%;margin-bottom:6px}
.btn-ghost:hover{background:#e5e7eb}
.btn-danger{background:#fff;color:#ef4444;border:1px solid #fecaca;width:100%}
.btn-danger:hover{background:#fef2f2}
.btn-sm{height:28px;font-size:12px;padding:0 10px;border-radius:6px}

/* status bar */
.status-bar{padding:10px 14px;border-radius:8px;border:1px solid #e5e7eb;background:#f9fafb;display:flex;align-items:center;gap:8px;margin-bottom:4px}
.status-bar.ok{background:#f0fdf4;border-color:#bbf7d0}
.status-bar.warn{background:#fffbeb;border-color:#fde68a}
.status-bar.danger{background:#fef2f2;border-color:#fecaca}
.status-bar.purple{background:#eef2ff;border-color:#c7d2fe}
.status-text{font-size:12px;font-weight:500}
.status-bar.ok .status-text{color:#15803d}
.status-bar.warn .status-text{color:#b45309}
.status-bar.danger .status-text{color:#dc2626}
.status-bar.purple .status-text{color:#4338ca}

/* main area */
.main{display:flex;flex-direction:column;overflow:hidden}
.main-header{padding:14px 20px;border-bottom:1px solid #e5e7eb;background:#fff;display:flex;align-items:center;justify-content:space-between}
.main-title{font-size:13px;font-weight:600;color:#111827}
.badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600}
.badge-gray{background:#f3f4f6;color:#6b7280}
.badge-blue{background:#eff6ff;color:#2563eb}
.badge-green{background:#f0fdf4;color:#15803d}
.badge-red{background:#fef2f2;color:#dc2626}
.badge-amber{background:#fffbeb;color:#b45309}
.badge-purple{background:#eef2ff;color:#4338ca}
.badge-indigo{background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe}

/* webhook list */
.webhook-list{overflow-y:auto;flex:1;padding:12px 20px;display:flex;flex-direction:column;gap:6px}

/* webhook card */
.wh-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;transition:border-color 0.15s;cursor:pointer}
.wh-card:hover{border-color:#a5b4fc}
.wh-card.open{border-color:#6366f1}
.wh-header{display:flex;align-items:center;gap:10px;padding:10px 14px}
.wh-seq{font-size:11px;color:#9ca3af;min-width:26px;font-variant-numeric:tabular-nums}
.wh-event{font-size:13px;font-weight:600;color:#111827;flex:1}
.wh-eid{font-size:11px;color:#9ca3af;font-family:'SF Mono',Monaco,monospace}
.wh-time{font-size:11px;color:#9ca3af;font-variant-numeric:tabular-nums;white-space:nowrap}
.wh-body{display:none;border-top:1px solid #f3f4f6;padding:14px}
.wh-card.open .wh-body{display:block}

/* tabs */
.tabs{display:flex;gap:2px;margin-bottom:12px;background:#f3f4f6;border-radius:7px;padding:3px}
.tab{padding:4px 12px;border-radius:5px;font-size:12px;font-weight:500;color:#6b7280;cursor:pointer;transition:all 0.15s}
.tab.active{background:#fff;color:#111827;box-shadow:0 1px 2px rgba(0,0,0,0.08)}

.tab-content{display:none}
.tab-content.active{display:block}

/* code block */
pre{background:#f9fafb;border:1px solid #e5e7eb;border-radius:7px;padding:12px;font-size:12px;font-family:'SF Mono',Monaco,'Courier New',monospace;overflow-x:auto;white-space:pre-wrap;word-break:break-all;color:#111827;line-height:1.6;max-height:260px;overflow-y:auto}

/* headers table */
.htable{width:100%;border-collapse:collapse;font-size:12px}
.htable td{padding:5px 8px;border-bottom:1px solid #f3f4f6;vertical-align:top}
.htable td:first-child{color:#6b7280;white-space:nowrap;width:42%;font-family:'SF Mono',Monaco,'Courier New',monospace;font-size:11px}
.htable td:last-child{color:#111827;word-break:break-all;font-family:'SF Mono',Monaco,'Courier New',monospace;font-size:11px}
.htable .hmac-key td:first-child{color:#059669;font-weight:600}
.htable .hmac-key td:last-child{color:#059669}

/* empty */
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:8px;color:#9ca3af}
.empty-icon{width:40px;height:40px;background:#f3f4f6;border-radius:10px;display:flex;align-items:center;justify-content:center}
.empty p{font-size:13px}
.empty .sub{font-size:12px;color:#d1d5db}

/* topbar controls */
.auto-label{display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280;cursor:pointer;white-space:nowrap}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <div class="live-dot" id="live-dot"></div>
    <span class="logo">webhook<span>.</span>receiver</span>
    <span class="badge badge-gray" id="count-badge">0 received</span>
  </div>
  <div class="topbar-right">
    <label class="auto-label">
      <input type="checkbox" id="auto-refresh" checked style="accent-color:#6366f1">
      Auto-refresh
    </label>
    <button class="btn btn-ghost btn-sm" onclick="clearWebhooks()">Clear log</button>
  </div>
</div>

<div class="layout">
  <div class="sidebar">

    <div>
      <div class="section-label">Current status</div>
      <div id="status-display"></div>
    </div>

    <div class="divider"></div>

    <div>
      <div class="section-label">Failure mode</div>
      <div class="mode-pills">
        <div class="mode-pill active" id="mode-normal" onclick="setMode('normal')">
          <div class="mode-pill-left">
            <span class="mode-pill-label">Normal</span>
            <span class="mode-pill-desc">Returns configured status code</span>
          </div>
          <div class="pill-check"><svg viewBox="0 0 10 10" fill="none" stroke="#fff" stroke-width="2"><polyline points="1.5,5 4,7.5 8.5,2.5"/></svg></div>
        </div>
        <div class="mode-pill" id="mode-flaky" onclick="setMode('flaky')">
          <div class="mode-pill-left">
            <span class="mode-pill-label">Flaky</span>
            <span class="mode-pill-desc">Fail N times then recover</span>
          </div>
          <div class="pill-check"><svg viewBox="0 0 10 10" fill="none" stroke="#fff" stroke-width="2"><polyline points="1.5,5 4,7.5 8.5,2.5"/></svg></div>
        </div>
        <div class="mode-pill" id="mode-timeout" onclick="setMode('timeout')">
          <div class="mode-pill-left">
            <span class="mode-pill-label">Timeout</span>
            <span class="mode-pill-desc">Never responds — triggers 10s timeout</span>
          </div>
          <div class="pill-check"><svg viewBox="0 0 10 10" fill="none" stroke="#fff" stroke-width="2"><polyline points="1.5,5 4,7.5 8.5,2.5"/></svg></div>
        </div>
      </div>
    </div>

    <div class="divider"></div>

    <div>
      <div class="section-label">Parameters</div>

      <div class="field">
        <label>Response status code</label>
        <input type="number" id="status_code" value="200" min="100" max="599">
        <span class="hint">200 = success, 500 = server error, 404 = not found</span>
      </div>

      <div class="field">
        <label>Response delay (seconds)</label>
        <input type="number" id="delay_seconds" value="0" min="0" step="0.5">
        <span class="hint">Simulates slow endpoints. Try 8s to test near-timeout.</span>
      </div>

      <div id="flaky-field" class="field" style="display:none">
        <label>Fail next N requests</label>
        <input type="number" id="fail_next_n" value="3" min="1">
        <span class="hint">After N failures it auto-recovers. Good for retry testing.</span>
      </div>

      <button class="btn btn-primary" onclick="applyConfig()">Apply</button>
      <button class="btn btn-ghost" onclick="resetConfig()">Reset to defaults</button>
    </div>

  </div>

  <div class="main">
    <div class="main-header">
      <span class="main-title">Incoming webhooks</span>
      <span style="font-size:12px;color:#9ca3af" id="endpoint-hint">POST http://test-receiver:9000/webhook</span>
    </div>
    <div class="webhook-list" id="webhook-list">
      <div class="empty">
        <p>No webhooks received yet</p>
        <p class="sub">Send an event from your API to see it here</p>
      </div>
    </div>
  </div>
</div>

<script>
let currentMode = 'normal';
let refreshInterval = null;

function setMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-pill').forEach(p => p.classList.remove('active'));
  document.getElementById('mode-' + mode).classList.add('active');
  document.getElementById('flaky-field').style.display = mode === 'flaky' ? 'flex' : 'none';

  if (mode === 'timeout') {
    document.getElementById('status_code').value = 200;
  } else if (mode === 'flaky') {
    document.getElementById('status_code').value = 200;
    document.getElementById('fail_next_n').value = 3;
  }
}

function statusClass(code) {
  if (code >= 200 && code < 300) return 'ok';
  if (code >= 400 && code < 500) return 'warn';
  if (code >= 500) return 'danger';
  return 'ok';
}

function updateStatusDisplay(cfg) {
  const el = document.getElementById('status-display');
  const dot = document.getElementById('live-dot');

  if (cfg.timeout_mode) {
    el.innerHTML = '<div class="status-bar purple"><div class="status-text">Timeout mode active — no responses</div></div>';
    dot.classList.add('off');
    return;
  }

  dot.classList.remove('off');

  let cls = statusClass(cfg.status_code);
  let lines = [];
  lines.push('<div class="status-bar ' + cls + '"><div class="status-text">Returning HTTP ' + cfg.status_code + '</div></div>');

  if (cfg.delay_seconds > 0) {
    lines.push('<div class="status-bar warn" style="margin-top:6px"><div class="status-text">' + cfg.delay_seconds + 's delay per request</div></div>');
  }

  if (cfg.fail_next_n > 0) {
    lines.push('<div class="status-bar danger" style="margin-top:6px"><div class="status-text">Failing next ' + (cfg.fail_next_n - cfg.fail_count) + ' of ' + cfg.fail_next_n + ' requests</div></div>');
  }

  el.innerHTML = lines.join('');
}

async function applyConfig() {
  const payload = {
    status_code: parseInt(document.getElementById('status_code').value),
    delay_seconds: parseFloat(document.getElementById('delay_seconds').value),
    fail_next_n: currentMode === 'flaky' ? parseInt(document.getElementById('fail_next_n').value) : 0,
    timeout_mode: currentMode === 'timeout',
  };
  const res = await fetch('/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const cfg = await res.json();
  updateStatusDisplay(cfg);
}

async function resetConfig() {
  const res = await fetch('/config/reset', { method: 'POST' });
  const cfg = await res.json();
  document.getElementById('status_code').value = cfg.status_code;
  document.getElementById('delay_seconds').value = cfg.delay_seconds;
  document.getElementById('fail_next_n').value = 3;
  setMode('normal');
  updateStatusDisplay(cfg);
}

async function clearWebhooks() {
  await fetch('/webhooks', { method: 'DELETE' });
  document.getElementById('webhook-list').innerHTML = emptyState();
  document.getElementById('count-badge').textContent = '0 received';
}

function emptyState() {
  return `<div class="empty">
    <p>No webhooks received yet</p><p class="sub">Send an event from your API to see it here</p></div>`;
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})
    + '.' + String(d.getMilliseconds()).padStart(3,'0');
}

function getHeader(headers, name) {
  return headers[name] || headers[name.toLowerCase()] || '';
}

function toggleCard(id) {
  const card = document.getElementById('wh-' + id);
  card.classList.toggle('open');
}

function switchTab(id, tab) {
  const card = document.getElementById('wh-' + id);
  card.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  card.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  card.querySelector('[data-tab="' + tab + '"]').classList.add('active');
  card.querySelector('[data-content="' + tab + '"]').classList.add('active');
}

function renderWebhooks(webhooks) {
  const list = document.getElementById('webhook-list');
  const badge = document.getElementById('count-badge');
  badge.textContent = webhooks.length + ' received';

  if (webhooks.length === 0) { list.innerHTML = emptyState(); return; }

  list.innerHTML = webhooks.map(wh => {
    const eventType = getHeader(wh.headers, 'x-webhook-event-type') || '(unknown)';
    const eventId = getHeader(wh.headers, 'x-webhook-event-id');
    const sig = getHeader(wh.headers, 'x-webhook-signature');
    const shortId = eventId ? eventId.substring(0,8) + '…' : '';

    const bodyStr = typeof wh.body === 'object'
      ? JSON.stringify(wh.body, null, 2) : String(wh.body);

    const headersHtml = Object.entries(wh.headers || {}).map(([k, v]) => {
      const isHmac = k.toLowerCase() === 'x-webhook-signature';
      return `<tr class="${isHmac ? 'hmac-key' : ''}"><td>${k}</td><td>${v}</td></tr>`;
    }).join('');

    return `<div class="wh-card" id="wh-${wh.id}" onclick="toggleCard(${wh.id})">
      <div class="wh-header">
        <span class="wh-seq">#${wh.id}</span>
        <span class="wh-event">${eventType}</span>
        ${shortId ? `<span class="wh-eid">${shortId}</span>` : ''}
        ${sig ? `<span class="badge badge-green">✓ HMAC</span>` : ''}
        <span class="wh-time">${fmtTime(wh.received_at)}</span>
      </div>
      <div class="wh-body">
        <div class="tabs" onclick="event.stopPropagation()">
          <div class="tab active" data-tab="payload" onclick="switchTab(${wh.id},'payload')">Payload</div>
          <div class="tab" data-tab="headers" onclick="switchTab(${wh.id},'headers')">Headers</div>
        </div>
        <div class="tab-content active" data-content="payload"><pre>${bodyStr}</pre></div>
        <div class="tab-content" data-content="headers" onclick="event.stopPropagation()">
          <table class="htable"><tbody>${headersHtml}</tbody></table>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function loadWebhooks() {
  const res = await fetch('/webhooks?limit=100');
  const data = await res.json();
  renderWebhooks(data);
}

async function loadConfig() {
  const res = await fetch('/config');
  const cfg = await res.json();
  document.getElementById('status_code').value = cfg.status_code;
  document.getElementById('delay_seconds').value = cfg.delay_seconds;
  if (cfg.timeout_mode) setMode('timeout');
  else if (cfg.fail_next_n > 0) setMode('flaky');
  updateStatusDisplay(cfg);
}

document.getElementById('auto-refresh').addEventListener('change', function() {
  if (this.checked) refreshInterval = setInterval(loadWebhooks, 2000);
  else clearInterval(refreshInterval);
});

loadConfig();
loadWebhooks();
refreshInterval = setInterval(loadWebhooks, 2000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)
