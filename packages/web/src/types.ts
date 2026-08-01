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
};

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
  meta?: Record<string, unknown>;
};
