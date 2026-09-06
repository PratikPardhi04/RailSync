export interface User {
  id: number
  name: string
  email: string
  role: 'engineer' | 'officer'
}

export interface LoginResponse {
  access_token: string
  user: User
}

export interface MaintenanceRequest {
  id: number
  engineer_id: number
  engineer_name?: string
  department: string
  maintenance_type: string
  location: string
  section: string
  requested_date: string
  preferred_start: string
  preferred_end: string
  duration_minutes: number
  priority: string
  description: string
  work_type?: string
  track_no?: string
  equipment?: string
  crew_size?: number
  est_material_cost?: number
  weather_sensitive?: string
  special_instructions?: string
  request_metadata?: Record<string, any>
  status: string
  current_version?: number
  created_at: string
  updated_at: string
}

export interface MaintenanceRequestCreate {
  department: string
  maintenance_type: string
  location: string
  section: string
  requested_date: string
  preferred_start: string
  preferred_end: string
  duration_minutes: number
  priority: string
  description: string
  work_type?: string
  track_no?: string
  equipment?: string
  crew_size?: number
  est_material_cost?: number
  weather_sensitive?: string
  special_instructions?: string
  request_metadata?: Record<string, any>
}

export interface AttachmentMeta {
  id: string
  name: string
  size: number
  sizeLabel: string
  type: string
}

export interface BlockPlan {
  id: number
  request_id: number
  version: number
  proposed_date: string
  start_time: string
  end_time: string
  duration_minutes: number
  score: number
  risk_score: number
  confidence: number
  affected_trains: AffectedTrain[]
  estimated_delay_minutes: number
  status: string
  block_id?: string
  report_data?: ReportData
  created_at: string
}

export interface WebSource {
  title?: string
  source_url?: string
  url?: string
  domain?: string
  snippet?: string
  content?: string
  relevance?: number
  score?: number
  authoritative?: boolean
  category?: string
  retrieved_at?: string
}

export interface ImpactRow extends AffectedTrain {
  projected_arrival?: string
}

export interface ReportData {
  request_summary?: Record<string, any>
  request_context?: {
    work_type?: string | null
    track_no?: string | null
    equipment?: string | null
    crew_size?: number | null
    est_material_cost?: number | null
    weather_sensitive?: string | null
    special_instructions?: string | null
    preferred_window?: string | null
  }
  cost_estimate?: {
    currency?: string
    material_cost?: number | null
    crew_size?: number | null
    estimated_crew_hours?: number | null
    note?: string
  }
  recommended_block?: Record<string, any>
  why_this_window?: string[]
  train_impact?: Record<string, any>
  impact_rows?: ImpactRow[]
  optimization?: Record<string, any>
  route_optimization?: Record<string, any>
  safety_compliance?: Record<string, any>
  risk?: Record<string, any>
  historical_evidence?: Record<string, any>
  rag_evidence?: Record<string, any>
  web_research_evidence?: { sources?: WebSource[]; note?: string }
  web_evidence?: { sources?: WebSource[]; note?: string }
  ai_explanation?: string
  ai_advisory?: { label?: string; is_final?: boolean; approval_authority?: string; note?: string }
  key_factors?: string[]
  tradeoffs?: string[]
  confidence?: number
  decision_evidence?: Record<string, any>
  priority_analysis?: Record<string, any>
  agent_assessments?: Record<string, any>
  risk_management_plan?: { mitigation: string }[]
  timeline?: Record<string, any>
  weather?: Record<string, any>
  alternative_routing_considered?: Record<string, any>
  ai_replanning?: { auto_replanned?: boolean; avoid_windows?: string[]; note?: string | null }
  version?: number
  officer_feedback?: Record<string, any> | null
  generated_at?: string
  officer_report?: OfficerReport
}

export interface OfficerExecutive {
  block_window?: string
  date?: string
  section?: string
  track_no?: string | null
  location?: string
  maintenance_type?: string
  duration_minutes?: number
  affected_trains?: number
  total_delay_minutes?: number
  max_delay_minutes?: number
  rerouted?: number
  held?: number
  risk_score?: number
  risk_level?: string
  confidence?: number
  solver_status?: string
  recommendation?: 'APPROVE' | 'REVIEW' | 'REJECT' | string
  auto_replanned?: boolean
  retry_count?: number
}

export interface OfficerTrainImpact {
  train_number: string
  train_name?: string
  train_type?: string
  priority?: string
  scheduled_arrival?: string
  scheduled_departure?: string
  delay_minutes?: number
  action?: string
  regulation?: string
  explanation?: string
}

export interface OfficerAlternativeWindow {
  window?: string
  duration_minutes?: number
  affected_trains?: number
  estimated_delay_minutes?: number
  score?: number
  within_preferred?: boolean
  avoids_officer_constraint?: boolean
  verdict?: 'SELECTED' | 'REJECTED' | string
  basis?: string[]
}

export interface OfficerRoutingAlternative {
  train_number?: string
  train_name?: string
  priority?: string
  delay_minutes?: number
  proposed_action?: string
  proposed_reasoning?: string
  decided_action?: string
  feasible?: boolean
  note?: string
  additional_delay?: number
}

export interface OfficerConstraintItem {
  rule?: string
  detail?: string
}

export interface OfficerRiskCategory {
  type?: string
  score?: number | null
  status?: string
  basis?: string
  mitigation?: string
}

export interface OfficerAgentFinding {
  agent: string
  role?: string
  summary?: string
  metrics?: Record<string, any>
}

export interface OfficerEvidenceGroup {
  source?: string
  tag?: 'FACT' | 'CALCULATION' | 'AI RECOMMENDATION' | string
  detail?: string
  items?: string[]
}

export interface OfficerReport {
  generated_for?: string
  grounding?: string
  executive?: OfficerExecutive
  selection_rationale?: {
    reasons?: string[]
    tradeoffs?: string[]
    alternative_windows_considered?: number
    preferred_window?: string
  }
  train_impact?: OfficerTrainImpact[]
  alternative_windows?: OfficerAlternativeWindow[]
  routing_alternatives?: OfficerRoutingAlternative[]
  constraints?: {
    valid?: boolean
    satisfied?: OfficerConstraintItem[]
    warnings?: OfficerConstraintItem[]
    violations?: OfficerConstraintItem[]
  }
  risk?: {
    overall_score?: number
    risk_level?: string
    categories?: OfficerRiskCategory[]
    warnings?: string[]
    mitigations?: string[]
  }
  agent_findings?: OfficerAgentFinding[]
  evidence_sources?: OfficerEvidenceGroup[]
  final_decision?: {
    authority?: string
    advisory?: string
    weight_of_evidence?: string
    benefits?: string[]
    residual_risks?: string[]
    mitigations?: string[]
    conditions?: string[]
  }
}

export interface AffectedTrain {
  train_number: string
  train_name: string
  train_type: string
  priority: string
  scheduled_arrival?: string
  scheduled_departure?: string
  arrival_time?: string
  departure_time?: string
  delay_minutes: number
  estimated_delay_minutes?: number
  action?: string
  status?: string
  impact?: string
}

export interface AgentResult {
  id?: number
  agent_name: string
  output_data: any
  reasoning_summary: string
  status: string
  plan_version?: number
  start_time?: string
  end_time?: string
}

export interface Report {
  plan: BlockPlan
  request: MaintenanceRequest
  agent_results: AgentResult[]
}

export interface EngineerDashboard {
  stats: {
    total_requests: number
    pending: number
    ai_processing: number
    awaiting_approval: number
    approved: number
    rejected: number
    published: number
    failed: number
  }
  recent_requests: (MaintenanceRequest & { latest_plan?: BlockPlan })[]
}

export interface OfficerDashboard {
  stats: {
    pending_approvals: number
    high_risk: number
    replanning: number
    approved_today: number
    published_blocks: number
  }
  pending_requests: (MaintenanceRequest & { latest_plan?: BlockPlan })[]
}

export interface RejectRequest {
  rejection_reason: string
  preferred_time?: string
  avoid_time?: string
  additional_constraint?: string
}

export interface HistoryEntry {
  version: number
  start_time: string
  end_time: string
  status: string
  risk_score: number
  block_id?: string
  created_at: string
}

export interface AuditEntry {
  actor: string
  action: string
  details: string
  timestamp: string
}

export interface WSMessage {
  event: string
  data: any
}

export interface LiveTrain {
  train_number: string
  train_name: string
  train_type: string
  priority: string
  origin: string
  destination: string
  section: string
  scheduled_arrival: string
  scheduled_departure: string
  projected_arrival: string
  status: string
  position: number
  delay_minutes: number
  held_by?: string | null
  premium: boolean
}

export interface LiveBlock {
  block_id: string
  plan_id: number
  version: number
  section: string
  maintenance_type: string
  window: string
  start: string
  end: string
  status: string
  live_phase: string
  active_now: boolean
}

export interface LiveConflict {
  train_number: string
  train_name: string
  priority: string
  block_id: string
  plan_id: number
  window: string
  projected_arrival: string
  delay_minutes: number
  severity: string
  auto_resolvable: boolean
}

export interface LiveEvent {
  time: string
  kind: string
  text: string
}

export interface LiveState {
  sim_date: string
  sim_time: string
  sim_minutes: number
  speed: number
  running: boolean
  trains: LiveTrain[]
  blocks: LiveBlock[]
  conflicts: LiveConflict[]
  events: LiveEvent[]
}

export interface WeatherInfo {
  source: string
  temperature_c: number
  precipitation_probability: number
  wind_kmh: number
  condition: string
  retrieved_at: string
}

export interface ExecutionInfo {
  plan_id: number
  version: number
  block_id?: string
  request_id: number
  section: string
  maintenance_type: string
  window: string
  proposed_date: string
  status: string
  sanctioned_by?: string | null
  sanctioned_at?: string | null
  checkin_at?: string | null
  block_active_at?: string | null
  released_at?: string | null
  completed_at?: string | null
  block_notice?: string | null
  caution_order?: string | null
  notes?: string | null
  plan_status: string
}
