"""Monitoring routes — view agent conversation traces.

- GET /admin/traces        → 最近 trace 列表 (JSON)
- GET /admin/traces/{id}   → 单条 trace 详情 (JSON)
- GET /admin/monitor       → 监测页面 (HTML)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(prefix="/admin", tags=["monitoring"])

_MONITOR_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Agent 监测台</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; background: #f5f6fa; color: #1f2328; }
  header { background: #24292f; color: #fff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 18px; margin: 0; }
  header .stats { font-size: 13px; opacity: .85; }
  .wrap { max-width: 1100px; margin: 20px auto; padding: 0 16px; }
  .toolbar { margin-bottom: 14px; display: flex; gap: 10px; align-items: center; }
  .toolbar input, .toolbar button { padding: 8px 12px; font-size: 13px; border: 1px solid #d0d7de; border-radius: 6px; }
  .toolbar button { background: #0969da; color: #fff; border: none; cursor: pointer; }
  .card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }
  .card .meta { font-size: 12px; color: #57606a; display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
  .msg { margin: 6px 0; font-size: 14px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .msg.user { color: #0969da; }
  .msg.agent { color: #1a7f37; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; margin-right: 6px; }
  .tag.err { background: #ffebe9; color: #cf222e; border: 1px solid #ff8182; }
  .tag.ok { background: #dafbe1; color: #1a7f37; border: 1px solid #4ac26b; }
  .tag.warn { background: #fff8c5; color: #9a6700; border: 1px solid #d4a72c; }
  .tag.info { background: #ddf4ff; color: #0969da; border: 1px solid #54aeff; }
  .tool { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 8px 10px; margin: 6px 0 6px 20px; font-size: 13px; }
  .tool .tname { font-weight: 600; }
  .tool .args { color: #57606a; font-family: ui-monospace, monospace; font-size: 12px; margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
  .tool .res { color: #1a7f37; font-size: 12px; margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
  .tool .fail { color: #cf222e; }
  .empty { color: #57606a; text-align: center; padding: 40px; }
  .detail { background: #f6f8fa; border-radius: 6px; padding: 10px 12px; margin-top: 8px; font-size: 13px; }
  .detail pre { margin: 4px 0; white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<header>
  <h1>🤖 Agent 对话监测台</h1>
  <div class="stats" id="stats"></div>
</header>
<div class="wrap">
  <div class="toolbar">
    <input id="q" placeholder="搜索：帕鲁名 / 工具名 / 错误关键词" style="flex:1">
    <button onclick="load()">刷新</button>
  </div>
  <div id="list"></div>
</div>
<script>
const ESC = (s) => (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function tag(trace) {
  let out = '';
  if (trace.had_error) out += '<span class="tag err">❌ 有错误</span>';
  if (trace.error) out += `<span class="tag warn">⚠️ ${ESC(trace.error.slice(0,40))}</span>`;
  if (trace.used_tools) out += '<span class="tag info">🔧 调工具</span>';
  if (trace.tool_success_rate < 1) out += `<span class="tag warn">工具成功率 ${Math.round(trace.tool_success_rate*100)}%</span>`;
  if (!trace.used_tools && !trace.had_error) out += '<span class="tag ok">纯对话</span>';
  return out;
}

function render(traces) {
  const el = document.getElementById('list');
  if (!traces.length) { el.innerHTML = '<div class="empty">暂无对话记录 —— 去前端发几条消息试试</div>'; return; }
  el.innerHTML = traces.map(t => {
    const tools = (t.llm_rounds||[]).flatMap(r => (r.tool_calls||[])).map(tc => `
      <div class="tool">
        <span class="tname ${tc.success?'':'fail'}">🔧 ${ESC(tc.name)} ${tc.success?'✓':'✗'}</span>
        <div class="args">参数: ${ESC(JSON.stringify(tc.arguments))}</div>
        ${tc.error ? `<div class="fail">错误: ${ESC(tc.error)}</div>` : `<div class="res">结果: ${ESC(JSON.stringify(tc.result).slice(0,200))}</div>`}
      </div>`).join('');
    return `<div class="card">
      <div class="meta">
        <span>🕐 ${ESC(t.ts)}</span>
        <span>⏱ ${t.latency_ms}ms</span>
        <span>📦 ${ESC(t.session_id)}</span>
        <span>👤 ${ESC(t.user_key)}</span>
        ${t.model ? `<span>🤖 ${ESC(t.model)}</span>` : ''}
        ${tag(t)}
      </div>
      <div class="msg user">🧑 <b>用户:</b> ${ESC(t.user_message)}</div>
      <div class="msg agent">🤖 <b>Agent:</b> ${ESC(t.reply)}</div>
      ${tools}
    </div>`;
  }).join('');
}

async function load() {
  const q = document.getElementById('q').value.trim();
  const url = q ? `/admin/traces?q=${encodeURIComponent(q)}` : '/admin/traces';
  const r = await fetch(url);
  const body = await r.json();
  render(body.data || []);
  document.getElementById('stats').textContent = `显示 ${(body.data||[]).length} 条`;
}
load();
</script>
</body>
</html>
"""


@router.get("/traces")
async def list_traces(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    q: str | None = None,
) -> dict:
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        return {"success": False, "data": [], "detail": "trace_store 未启用"}
    traces = await store.list_recent(limit=limit)
    # 简单搜索：按用户消息/回复/工具名/错误过滤
    if q:
        ql = q.lower()
        traces = [
            t
            for t in traces
            if ql in t.user_message.lower()
            or ql in t.reply.lower()
            or ql in t.error.lower()
            or any(
                ql in tc.name.lower()
                for r in t.llm_rounds
                for tc in r.tool_calls
            )
        ]
    data = [
        {
            "trace_id": t.trace_uid,
            "session_id": t.session_id,
            "user_key": t.user_key,
            "user_message": t.user_message,
            "reply": t.reply,
            "model": t.model,
            "llm_rounds": [
                {
                    "round": r.round,
                    "requested_tools": r.requested_tools,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "success": tc.success,
                            "error": tc.error,
                        }
                        for tc in r.tool_calls
                    ],
                }
                for r in t.llm_rounds
            ],
            "error": t.error,
            "latency_ms": t.latency_ms,
            "used_tools": t.used_tools,
            "had_error": t.had_error,
            "tool_success_rate": t.tool_success_rate,
            "reply_length": t.reply_length,
            "ts": t.ts,
        }
        for t in traces
    ]
    return {"success": True, "data": data}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request) -> dict:
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="trace_store 未启用")
    trace = await store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return {
        "success": True,
        "data": {
            "trace_id": trace.trace_uid,
            "session_id": trace.session_id,
            "user_key": trace.user_key,
            "user_message": trace.user_message,
            "reply": trace.reply,
            "model": trace.model,
            "llm_rounds": [
                {
                    "round": r.round,
                    "requested_tools": r.requested_tools,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "success": tc.success,
                            "error": tc.error,
                        }
                        for tc in r.tool_calls
                    ],
                }
                for r in trace.llm_rounds
            ],
            "error": trace.error,
            "latency_ms": trace.latency_ms,
            "used_tools": trace.used_tools,
            "had_error": trace.had_error,
            "tool_success_rate": trace.tool_success_rate,
            "reply_length": trace.reply_length,
            "ts": trace.ts,
        },
    }


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_page() -> HTMLResponse:
    return HTMLResponse(_MONITOR_HTML)
