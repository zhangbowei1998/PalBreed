import { useState } from "react";
import type { AgentTraceInfo } from "../types";

type Props = {
  trace: AgentTraceInfo | null;
};

function shortName(name: string): string {
  const map: Record<string, string> = {
    query_parent_pairs: "查询配种方案",
    resolve_pal: "解析帕鲁",
    query_top_suitability: "查询工种最强",
    query_pal_stats: "查询帕鲁属性",
    query_stats: "查询统计",
  };
  return map[name] ?? name;
}

function summarizeResult(result: Record<string, unknown> | undefined, name: string): string {
  if (!result) return "";
  if (name === "query_top_suitability") {
    const cands = (result.candidates ?? []) as Array<{ cn_name?: string; matched_level?: number }>;
    if (cands.length) {
      return cands.map((c) => `${c.cn_name ?? "?"}(${c.matched_level ?? 0}级)`).join("、");
    }
  }
  if (name === "query_parent_pairs") {
    const pal = result.pal as { cn_name?: string } | undefined;
    const pairs = (result.parent_pairs ?? []) as Array<{ parent_a?: string; parent_b?: string }>;
    if (pairs.length) {
      return `${pal?.cn_name ?? "?"} 共 ${result.total ?? pairs.length} 种方案`;
    }
  }
  const s = JSON.stringify(result);
  return s.length > 120 ? `${s.slice(0, 120)}…` : s;
}

export function ThinkingProcess({ trace }: Props) {
  const [open, setOpen] = useState(false);
  if (!trace) return null;

  const tools = trace.tool_calls ?? [];
  const hasTools = trace.used_tools && tools.length > 0;

  return (
    <div className={`thinking ${hasTools ? "has-tools" : ""}`}>
      <button
        type="button"
        className="thinking-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="thinking-dot" aria-hidden="true" />
        {hasTools
          ? (
            <>
              <span className="thinking-title">
                思考过程 · 调用 {tools.length} 个工具
              </span>
              <span className="thinking-tools">
                {tools.map((tc, i) => (
                  <span key={i} className={`thinking-tool-chip ${tc.success ? "ok" : "fail"}`}>
                    {shortName(tc.name)} {tc.success ? "✓" : "✗"}
                  </span>
                ))}
              </span>
            </>
          )
          : (
            <span className="thinking-title">
              直接回答{trace.latency_ms ? ` · ${trace.latency_ms}ms` : ""}
            </span>
          )}
        <span className={`thinking-arrow ${open ? "open" : ""}`}>▸</span>
      </button>

      {open && (
        <div className="thinking-body">
          <div className="thinking-meta">
            {trace.model && <span>模型: {trace.model}</span>}
            <span>耗时: {trace.latency_ms}ms</span>
            {trace.had_error && <span className="thinking-err">存在错误</span>}
          </div>
          {hasTools ? (
            tools.map((tc, i) => (
              <div key={i} className={`tool-card ${tc.success ? "" : "tool-card-fail"}`}>
                <div className="tool-card-head">
                  <span className="tool-card-name">{shortName(tc.name)}</span>
                  <span className={`tool-card-status ${tc.success ? "ok" : "fail"}`}>
                    {tc.success ? "成功" : "失败"}
                  </span>
                </div>
                <div className="tool-card-row">
                  <span className="tool-card-label">参数</span>
                  <code>{JSON.stringify(tc.arguments)}</code>
                </div>
                {tc.error && (
                  <div className="tool-card-row">
                    <span className="tool-card-label">错误</span>
                    <code className="err">{tc.error}</code>
                  </div>
                )}
                {tc.success && tc.result && (
                  <div className="tool-card-row">
                    <span className="tool-card-label">结果</span>
                    <code>{summarizeResult(tc.result, tc.name) || JSON.stringify(tc.result)}</code>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="thinking-note">未调用工具，Agent 直接基于上下文回答。</div>
          )}
        </div>
      )}
    </div>
  );
}
