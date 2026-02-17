// ── Request types ─────────────────────────────────────────

export interface AskRequest {
  question: string
  protocol?: 'consensus' | 'voting' | 'auto'
  rounds?: number
  decompose?: boolean
  tools?: boolean
}

export interface FeedbackRequest {
  thread_id: string
  result: 'success' | 'failure' | 'partial'
  notes?: string | null
}

// ── Response types ────────────────────────────────────────

export interface AskResponse {
  decision: string
  confidence: number
  dissent: string | null
  cost: number
  thread_id: string | null
  protocol_used: string
}

export interface ThreadSummary {
  thread_id: string
  question: string
  status: string
  created_at: string
}

export interface ThreadListResponse {
  threads: ThreadSummary[]
  total: number
}

export interface Contribution {
  model_ref: string
  role: string
  content: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
}

export interface Decision {
  content: string
  confidence: number
  dissent: string | null
}

export interface Turn {
  round_number: number
  state: string
  contributions: Contribution[]
  decision: Decision | null
}

export interface ThreadDetail {
  thread_id: string
  question: string
  status: string
  created_at: string
  turns: Turn[]
}

export interface RecallResult {
  thread_id: string
  question: string
  decision: string | null
  confidence: number | null
}

export interface RecallResponse {
  results: RecallResult[]
  query: string
}

export interface FeedbackResponse {
  status: string
  thread_id: string
}

export interface ModelInfo {
  provider_id: string
  model_id: string
  display_name: string
  context_window: number
  max_output_tokens: number
  input_cost_per_mtok: number
  output_cost_per_mtok: number
}

export interface ModelsResponse {
  models: ModelInfo[]
  total: number
}

export interface CostByModel {
  model_ref: string
  cost: number
  calls: number
}

export interface CostResponse {
  total_cost: number
  total_input_tokens: number
  total_output_tokens: number
  by_model: CostByModel[]
}

export interface HealthResponse {
  status: string
}

// ── Decision Space types ──────────────────────────────────

export interface SpaceDecision {
  id: string
  thread_id: string
  question: string
  confidence: number
  intent: string | null
  category: string | null
  genus: string | null
  outcome: string | null
  created_at: string
}

export interface SpaceAxisMeta {
  categories: string[]
  genera: string[]
}

export interface DecisionSpaceResponse {
  decisions: SpaceDecision[]
  axes: SpaceAxisMeta
  total: number
}

// ── WebSocket event types ─────────────────────────────────

export type WSEventType =
  | 'phase_start'
  | 'phase_complete'
  | 'challenge'
  | 'commit'
  | 'complete'
  | 'error'

export type ConsensusPhase = 'PROPOSE' | 'CHALLENGE' | 'REVISE' | 'COMMIT'

export interface WSPhaseStart {
  type: 'phase_start'
  phase: ConsensusPhase
  model?: string
  models?: string[]
  round: number
}

export interface WSPhaseComplete {
  type: 'phase_complete'
  phase: ConsensusPhase
  content?: string
}

export interface WSChallenge {
  type: 'challenge'
  model: string
  content: string
}

export interface WSCommit {
  type: 'commit'
  confidence: number
  dissent: string | null
  round: number
}

export interface WSComplete {
  type: 'complete'
  decision: string
  confidence: number
  dissent: string | null
  cost: number
  thread_id: string | null
}

export interface WSError {
  type: 'error'
  message: string
}

export type WSEvent =
  | WSPhaseStart
  | WSPhaseComplete
  | WSChallenge
  | WSCommit
  | WSComplete
  | WSError

// ── API Error ─────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}
