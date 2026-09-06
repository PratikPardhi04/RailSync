from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

class MaintenanceRequestCreate(BaseModel):
    department: str
    maintenance_type: str
    location: str
    section: str
    requested_date: str
    preferred_start: str
    preferred_end: str
    duration_minutes: int
    priority: str
    description: str = ""
    work_type: Optional[str] = None
    track_no: Optional[str] = None
    equipment: Optional[str] = None
    crew_size: Optional[int] = None
    est_material_cost: Optional[float] = None
    weather_sensitive: Optional[str] = None
    special_instructions: Optional[str] = None
    request_metadata: Optional[dict] = None

class MaintenanceRequestResponse(BaseModel):
    id: int
    engineer_id: int
    department: str
    maintenance_type: str
    location: str
    section: str
    requested_date: str
    preferred_start: str
    preferred_end: str
    duration_minutes: int
    priority: str
    description: str
    work_type: Optional[str] = None
    track_no: Optional[str] = None
    equipment: Optional[str] = None
    crew_size: Optional[int] = None
    est_material_cost: Optional[float] = None
    weather_sensitive: Optional[str] = None
    special_instructions: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    engineer_name: Optional[str] = None
    current_version: Optional[int] = None

class BlockPlanResponse(BaseModel):
    id: int
    request_id: int
    version: int
    proposed_date: str
    start_time: str
    end_time: str
    duration_minutes: int
    score: float
    risk_score: float
    confidence: float
    affected_trains: Any
    estimated_delay_minutes: float
    status: str
    block_id: Optional[str] = None
    created_at: datetime

class RejectRequest(BaseModel):
    rejection_reason: str
    preferred_time: Optional[str] = None
    avoid_time: Optional[str] = None
    additional_constraint: Optional[str] = None

class AgentResultResponse(BaseModel):
    id: int
    agent_name: str
    output_data: Any
    reasoning_summary: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class DashboardStats(BaseModel):
    total_requests: int
    pending: int
    ai_processing: int
    awaiting_approval: int
    approved: int
    rejected: int
    published: int
    replanning: int

class OfficerDashboardStats(BaseModel):
    pending_approvals: int
    high_risk: int
    replanning: int
    approved_today: int
    published_blocks: int
