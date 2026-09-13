// Shapes of the FastAPI responses and stream events (see main.py and agent/pipeline.py).

export type AgentKey = "researcher" | "tailor" | "executor"
export type AppKey = "gmail" | "calendar" | "crm" | "slack"
export type Outcome = "sent" | "drafted" | "partial" | "flagged" | "duplicate"

export interface ActionResult {
  status: string
  detail: string
  sent?: boolean
  link?: string | null
}

export interface Receipt {
  tailored: string
  source_line: number | null
  supported: boolean
  reason: string
}

export interface Requirements {
  skills?: string[]
  seniority?: string
  must_haves?: string[]
  keywords?: string[]
}

export interface GapReport {
  missing_must_haves: string[]
  missing_keywords: string[]
  unsupported_claims: string[]
  seniority?: string | null
}

export interface RunResult {
  run_id: string
  company: string
  role: string
  candidate?: string
  requirements: Requirements
  resume_lines: string[]
  github?: {
    username: string
    verified: { skill: string; repos: { name: string; url: string }[] }[]
    error: string | null
  }
  cover_note: string
  guardrail: { score: number; threshold: number; needs_review: boolean }
  executor_verdict: {
    recommendation: string
    confidence: number
    reason: string
    faithful: boolean
    unsupported_claims: string[]
    receipts: Receipt[]
  }
  executor_mode: string
  gap_report: GapReport
  outcome: Outcome
  actions: Record<string, ActionResult>
  used_live_llm: boolean
}

export interface BatchSummaryItem {
  run_id?: string
  company: string
  role: string
  outcome: string
}

export type PipelineEvent =
  | { type: "step"; step: AgentKey; status: string }
  | { type: "tool"; app: AppKey; status: string; detail?: string }
  | { type: "fault"; names: string[] }
  | { type: "github"; verified: string[]; error: string | null }
  | { type: "result"; result: RunResult }
  | { type: "error"; detail: string }
  | { type: "batch"; index: number; total: number; company: string; role: string }
  | { type: "batch_done"; summary: BatchSummaryItem[] }

export interface Status {
  llm: boolean
  model: string
  google: boolean
  crm: boolean
  slack: boolean
  review_threshold: number
  send_threshold: number
  faults: string[]
  available_faults: string[]
}

export interface Connections {
  composio: boolean
  apps: Record<AppKey, { connected: boolean; via: "composio" | "env" | null }>
}

export interface Job {
  source?: string
  title: string
  company_name: string
  location?: string
  posted?: string
  description: string
  url: string
  tags?: string[]
}

export interface RecommendedJob extends Job {
  match_score: number
  matched_skills: string[]
  github_skills: string[]
  senior_role: boolean
}

export interface HistoryRow {
  run_id: string
  started_at: string
  company: string
  role: string
  outcome: Outcome
  executor_mode: string | null
  faults: string[] | null
  undone: boolean | null
  replied: boolean | null
  reply_link: string | null
  overlap: number
}

export interface EvalRow {
  jd_file: string
  outcome?: string
  overlap?: number
  error?: string
  extraction: boolean
  faithfulness: boolean
  decision: boolean
  actions: boolean
  passed: boolean
  fell_back?: string[]
}

export interface EvalSummary {
  ran_at: string
  faults: string[]
  total: number
  passed: number
  criteria: Record<string, number>
  rows: EvalRow[]
}

export const APP_LABELS: Record<AppKey, string> = {
  gmail: "Gmail",
  calendar: "Calendar",
  crm: "HubSpot",
  slack: "Slack",
}

export const OUTCOMES: Record<Outcome, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  sent: { label: "Sent", variant: "default" },
  drafted: { label: "Drafted", variant: "secondary" },
  partial: { label: "Partly failed", variant: "destructive" },
  flagged: { label: "Flagged for review", variant: "outline" },
  duplicate: { label: "Duplicate, skipped", variant: "outline" },
}
