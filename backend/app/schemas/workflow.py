"""RailLink AI - Strongly typed workflow schemas.

Every agent and deterministic engine publishes data that conforms to one of
these Pydantic models. LLM output is validated against these schemas before it
is allowed to enter graph state; free-form LLM prose never becomes system state
used for decisions.

Schemas are intentionally permissive on *extra* keys (we preserve legacy
front-facing keys) but strict about the structural fields the workflow depends
on.
"""
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RailBModel(BaseModel):
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


class MaintenanceAnalysis(RailBModel):
    maintenance_duration: int = 0
    resource_requirements: List[Any] = Field(default_factory=list)
    priority: str = "MEDIUM"
    maintenance_constraints: List[Any] = Field(default_factory=list)
    section: str = ""
    summary: str = ""
    urgency: str = "MEDIUM"
    preferred_start: str = "10:00"
    preferred_end: str = "14:00"
    requested_date: str = ""
    execution_time: float = 0.0
    llm_enhanced: bool = False


class TrafficAnalysis(RailBModel):
    affected_trains: List[Dict[str, Any]] = Field(default_factory=list)
    conflict_windows: List[Dict[str, Any]] = Field(default_factory=list)
    traffic_density: int = 0
    total_affected: int = 0
    total_estimated_delay: float = 0.0
    estimated_impact: str = "LOW"
    section: str = ""
    analysis_window: str = ""
    summary: str = ""
    execution_time: float = 0.0


class PriorityAnalysis(RailBModel):
    priority_score: float = 0.0
    priority_level: str = "MEDIUM"
    safety_criticality: float = 0.0
    asset_criticality: float = 0.0
    maintenance_urgency: float = 0.0
    operational_impact: float = 0.0
    passenger_impact: float = 0.0
    reason: str = "Standard priority assessment"
    execution_time: float = 0.0


class HistoricalCase(RailBModel):
    case_id: str = ""
    section: str = ""
    maintenance_type: str = ""
    duration: int = 0
    proposed_window: str = ""
    outcome: str = ""
    affected_trains: int = 0
    delay_minutes: int = 0
    date: str = ""
    similarity_score: float = 0.0


class RailwayRule(RailBModel):
    rule_id: str = ""
    title: str = ""
    source: str = ""
    content: str = ""
    relevance: float = 0.0


class HistoricalAnalysis(RailBModel):
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_rules: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    historical_outcomes: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    execution_time: float = 0.0


class RAGEvidence(RailBModel):
    """RAG is evidence, never a hard constraint by itself."""

    query: str = ""
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    total_retrieved: int = 0
    engine: str = "faiss"


class WebSource(RailBModel):
    """One retrieved web source (Tavily). Evidence only, never a constraint."""

    query: str = ""
    source_url: str = ""
    title: str = ""
    snippet: str = ""
    relevance: float = 0.0
    score: float = 0.0
    domain: str = ""
    authoritative: bool = False
    published_date: Optional[str] = None
    sample: bool = False


class WebSearchEvidence(RailBModel):
    """Tavily web research output.

    status: idle | completed | failed. Web evidence may enrich the officer
    report but must NEVER modify hard constraints, schedules, or the outcome of
    deterministic engines (CP-SAT, simulator, validator, hard-conflict gate).
    """

    query: str = ""
    total_searches: int = 0
    total_results: int = 0
    relevant_results: int = 0
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "idle"
    error: Optional[str] = None
    search_count: int = 0
    search_depth: str = "basic"
    summary: str = ""
    sample: bool = False
    execution_time: float = 0.0


class CandidateWindow(RailBModel):
    start_time: str = ""
    end_time: str = ""
    duration_minutes: int = 0
    affected_trains: int = 0
    estimated_delay_minutes: float = 0.0
    score: float = 0.0
    avoids_officer_constraint: bool = False
    within_preferred: bool = False


class CandidateGenerationResult(RailBModel):
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    total_evaluated: int = 0
    constraints_applied: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    execution_time: float = 0.0


# ---------------------------------------------------------------------------
# Deterministic engine outputs
# ---------------------------------------------------------------------------


class OptimizationResult(RailBModel):
    feasible: bool = False
    selected_window: Optional[Dict[str, Any]] = None
    objective_score: float = 0.0
    affected_trains: int = 0
    estimated_delay_minutes: float = 0.0
    all_candidates_scores: List[Dict[str, Any]] = Field(default_factory=list)
    constraints_satisfied: bool = False
    solver_status: str = "UNKNOWN"
    violations: List[str] = Field(default_factory=list)
    execution_time: float = 0.0


class TrainImpact(RailBModel):
    affected_trains: List[Dict[str, Any]] = Field(default_factory=list)
    total_trains_affected: int = 0
    total_delay_minutes: float = 0.0
    max_delay_minutes: float = 0.0
    trains_rerouted: int = 0
    trains_held: int = 0
    trains_delayed: int = 0
    simulation_block: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    execution_time: float = 0.0


class RoutingOption(RailBModel):
    train_number: str = ""
    train_name: str = ""
    priority: str = ""
    action: str = "NORMAL"  # NORMAL | HOLD | DIVERT | RESCHEDULE | NO_ACTION
    minutes_hold: int = 0
    route_id: Optional[str] = None
    reschedule_to: Optional[str] = None
    reasoning: str = ""


class RoutingAnalysis(RailBModel):
    """Alternative Routing & Regulation Agent output.

    The agent ONLY proposes options. It can reference a route_id only if that
    route exists in the network topology data (enforced on validation).
    """

    section: str = ""
    options: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    notes: List[str] = Field(default_factory=list)
    execution_time: float = 0.0


class RoutingOptimizationResult(RailBModel):
    """Deterministic Route & Operations Optimizer output.

    Validates every proposed option against network topology + capacity and
    picks the lowest-impact feasible per-train action. Feasibility is decided
    here, never by the LLM.
    """

    options: List[Dict[str, Any]] = Field(default_factory=list)
    feasible: bool = True
    total_additional_delay: float = 0.0
    trains_rerouted: int = 0
    trains_held: int = 0
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    execution_time: float = 0.0


class ConstraintValidation(RailBModel):
    valid: bool = False
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    passed_constraints: List[Dict[str, Any]] = Field(default_factory=list)
    total_checks: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    execution_time: float = 0.0


class RiskAnalysis(RailBModel):
    risk_score: float = 0.0
    risk_level: str = "MEDIUM"
    safety_risk: float = 0.0
    operational_risk: float = 0.0
    maintenance_risk: float = 0.0
    passenger_impact: float = 0.0
    compliance_status: str = "UNKNOWN"
    rules_used: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    mitigations: List[str] = Field(default_factory=list)
    summary: str = ""
    execution_time: float = 0.0


class DecisionRecommendation(RailBModel):
    """Decision Fusion output.

    Advisory only - can explain the CP-SAT result but never change it, and the
    officer remains the sole approval authority.
    """

    recommendation: Literal["RECOMMEND_APPROVE", "RECOMMEND_REVIEW"] = "RECOMMEND_REVIEW"
    recommendation_is_final: bool = False
    approval_authority: str = "OFFICER"
    reasoning_summary: str = ""
    why_this_window: List[str] = Field(default_factory=list)
    key_factors: List[Dict[str, Any]] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    execution_time: float = 0.0


# ---------------------------------------------------------------------------
# Feedback / constraints
# ---------------------------------------------------------------------------


class ReplanningConstraint(RailBModel):
    """A structured, machine-checkable planning constraint derived from
    officer feedback or an AI auto-replan decision."""

    type: Literal["AVOID_WINDOW", "PREFERRED_TIME", "ADDITIONAL"] = "AVOID_WINDOW"
    start: Optional[str] = None  # HH:MM
    end: Optional[str] = None    # HH:MM
    reason: Optional[str] = None
    source: Literal["OFFICER", "AUTO"] = "OFFICER"


class OfficerFeedback(RailBModel):
    rejection_reason: Optional[str] = None
    preferred_time: Optional[str] = None
    avoid_time: Optional[str] = None
    additional_constraint: Optional[str] = None
    constraints: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report + workflow state
# ---------------------------------------------------------------------------


class PlanReport(RailBModel):
    request_summary: Dict[str, Any] = Field(default_factory=dict)
    recommended_block: Dict[str, Any] = Field(default_factory=dict)
    why_this_window: List[str] = Field(default_factory=list)
    candidate_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    train_impact: Dict[str, Any] = Field(default_factory=dict)
    alternative_routing_considered: List[Dict[str, Any]] = Field(default_factory=list)
    optimization: Dict[str, Any] = Field(default_factory=dict)
    safety_compliance: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    historical_evidence: Dict[str, Any] = Field(default_factory=dict)
    rag_evidence: Dict[str, Any] = Field(default_factory=dict)
    ai_explanation: str = ""
    ai_advisory: Dict[str, Any] = Field(default_factory=dict)
    key_factors: List[Dict[str, Any]] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    decision_evidence: Dict[str, Any] = Field(default_factory=dict)
    priority_analysis: Dict[str, Any] = Field(default_factory=dict)
    agent_assessments: Dict[str, Any] = Field(default_factory=dict)
    risk_management_plan: List[Dict[str, Any]] = Field(default_factory=list)
    weather: Dict[str, Any] = Field(default_factory=dict)
    timeline: Dict[str, Any] = Field(default_factory=dict)
    ai_replanning: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    officer_feedback: Optional[Dict[str, Any]] = None
    generated_at: str = ""


class WorkflowState(RailBModel):
    """LangGraph shared graph state (Pydantic schema).

    LLM/engine outputs are stored as validated model instances (or their
    `.model_dump()` dicts where the downstream consumer needs plain data).
    """

    request_id: int = 0
    plan_version: int = 1
    run_id: str = ""
    request: Dict[str, Any] = Field(default_factory=dict)
    trains: List[Dict[str, Any]] = Field(default_factory=list)
    officer_feedback: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    workflow_status: str = "RUNNING"
    errors: List[str] = Field(default_factory=list)

    maintenance_analysis: Optional[MaintenanceAnalysis] = None
    traffic_analysis: Optional[TrafficAnalysis] = None
    priority_analysis: Optional[PriorityAnalysis] = None
    historical_analysis: Optional[HistoricalAnalysis] = None
    rag_evidence: Optional[RAGEvidence] = None
    web_evidence: Optional[WebSearchEvidence] = None

    candidate_windows: Optional[CandidateGenerationResult] = None
    optimization_result: Optional[OptimizationResult] = None
    simulation_result: Optional[TrainImpact] = None
    routing_analysis: Optional[RoutingAnalysis] = None
    routing_optimization: Optional[RoutingOptimizationResult] = None
    constraint_validation: Optional[ConstraintValidation] = None
    risk_analysis: Optional[RiskAnalysis] = None
    decision: Optional[DecisionRecommendation] = None

    replanning_constraints: List[Any] = Field(default_factory=list)
    auto_replanned: bool = False
    auto_avoid_windows: List[Any] = Field(default_factory=list)

    report: Optional[PlanReport] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    start_time: float = 0.0
    total_execution_time: float = 0.0


def state_from_dict(data: Dict[str, Any]) -> WorkflowState:
    """Build a validated WorkflowState from a plain dict (request inputs)."""
    return WorkflowState(
        request_id=int(data.get("id", 0)),
        request=data,
        start_time=__import__("time").time(),
    )


def hours_minutes_to_mins(hhmm: str) -> int:
    m = re.match(r"(\d{1,2}):(\d{2})", str(hhmm).strip())
    if not m:
        return 0
    return int(m.group(1)) * 60 + int(m.group(2))


def to_time_str(minutes: int) -> str:
    minutes = int(minutes) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"