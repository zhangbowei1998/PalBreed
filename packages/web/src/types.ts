export type AgentRole = "assistant" | "user";

export type PalProfile = {
  id: string;
  number: number;
  cn_name: string;
  en_name: string;
  combi_rank: number;
  rarity: number;
  is_wild: boolean;
  image_url?: string | null;
  wiki_url?: string | null;
};

export type ChatMessage = {
  id: string;
  role: AgentRole;
  content: string;
  trace?: AgentTraceInfo | null;
  data_cards?: DataCard[];
};

// ── 结构化数据卡片（Agent 工具结果 → 前端渲染） ──

export type PassiveCard = {
  type: "passive";
  passive: string;
  pals: Array<{ id?: string; cn_name?: string; passive_rank?: number }>;
  total: number;
};

export type DropCard = {
  type: "drop";
  item: string;
  pals: Array<{ pal_id?: string; pal_cn?: string; rate?: number; is_boss?: boolean }>;
  total: number;
};

export type RecipeCard = {
  type: "recipe";
  item: string;
  recipe: Array<{ station?: string; material?: string; count?: number }>;
  total: number;
};

export type SkillsCard = {
  type: "skills";
  pal: { id?: string; cn_name?: string };
  skills: Array<{ waza_id?: string; cn_name?: string; learn_level?: number; element?: string; power?: number }>;
  total: number;
};

export type PalDetailCard = {
  type: "pal_detail";
  pal_id?: string;
  cn_name?: string;
  stats?: Record<string, number | string>;
  skill_count?: number;
  drop_count?: number;
};

export type DataCard = PassiveCard | DropCard | RecipeCard | SkillsCard | PalDetailCard;

export type AgentAction = {
  action:
    | "expand_parent"
    | "confirm_target"
    | "select_parent_pair"
    | "continue_from_parent";
  label: string;
  payload: Record<string, unknown>;
};

export type AgentStateSnapshot = {
  session_id: string;
  target_pal: string | null;
  target_candidates: Array<{
    pal_id: string;
    cn_name: string;
    score: number;
    reason: string;
  }>;
  explored_nodes: string[];
  edges: Array<{
    child_pal_id: string;
    parent_a_id: string;
    parent_a_name: string;
    parent_b_id: string;
    parent_b_name: string;
    method: string;
    depth: number;
  }>;
  click_trace: Array<{ pal_id: string; ts: string }>;
  pending_frontier?: string[];
  node_depths?: Record<string, number>;
  selected_pairs?: Array<{
    child_pal_id: string;
    parent_a_id: string;
    parent_a_name: string;
    parent_b_id: string;
    parent_b_name: string;
    method: string;
    depth: number;
  }>;
};

export type AgentData = {
  messages: Array<{ role: "assistant"; content: string }>;
  actions: AgentAction[];
  state_snapshot: AgentStateSnapshot;
  data_cards?: DataCard[];
  meta?: Record<string, unknown>;
};

export type AgentToolCall = {
  name: string;
  arguments: Record<string, unknown>;
  success: boolean;
  error?: string;
  result?: Record<string, unknown>;
};

export type AgentTraceInfo = {
  latency_ms: number;
  model: string;
  used_tools: boolean;
  had_error: boolean;
  tool_success_rate: number;
  tool_calls: AgentToolCall[];
};
