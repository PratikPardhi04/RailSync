from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    requests = relationship("MaintenanceRequest", back_populates="engineer")

class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("users.id"))
    department = Column(String(50), nullable=False)
    maintenance_type = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)
    section = Column(String(200), nullable=False)
    requested_date = Column(String(20), nullable=False)
    preferred_start = Column(String(10), nullable=False)
    preferred_end = Column(String(10), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    priority = Column(String(20), nullable=False)
    description = Column(Text, default="")
    work_type = Column(String(50), nullable=True)
    track_no = Column(String(30), nullable=True)
    equipment = Column(String(200), nullable=True)
    crew_size = Column(Integer, nullable=True)
    est_material_cost = Column(Float, nullable=True)
    weather_sensitive = Column(String(10), nullable=True)
    special_instructions = Column(Text, nullable=True)
    request_metadata = Column(JSON, default=dict)
    status = Column(String(30), default="DRAFT")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    engineer = relationship("User", back_populates="requests")
    plans = relationship("BlockPlan", back_populates="request")
    agent_results = relationship("AgentResult", back_populates="request")
    decisions = relationship("OfficerDecision", back_populates="request")
    audit_logs = relationship("AuditLog", back_populates="request")

class Train(Base):
    __tablename__ = "trains"
    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), unique=True, nullable=False)
    train_name = Column(String(100), nullable=False)
    train_type = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False)
    origin = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)
    section = Column(String(200), nullable=False)
    arrival_time = Column(String(10), nullable=False)
    departure_time = Column(String(10), nullable=False)
    average_speed = Column(Integer, default=80)

class BlockPlan(Base):
    __tablename__ = "block_plans"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"))
    version = Column(Integer, default=1)
    proposed_date = Column(String(20), nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    score = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    affected_trains = Column(JSON, default=list)
    estimated_delay_minutes = Column(Float, default=0.0)
    status = Column(String(30), default="GENERATED")
    block_id = Column(String(50), nullable=True)
    report_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    request = relationship("MaintenanceRequest", back_populates="plans")

class AgentResult(Base):
    __tablename__ = "agent_results"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"))
    plan_version = Column(Integer, default=1)
    agent_name = Column(String(50), nullable=False)
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    reasoning_summary = Column(Text, default="")
    status = Column(String(20), default="pending")
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    request = relationship("MaintenanceRequest", back_populates="agent_results")

class OfficerDecision(Base):
    __tablename__ = "officer_decisions"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"))
    plan_version = Column(Integer, nullable=False)
    officer_id = Column(Integer, ForeignKey("users.id"))
    decision = Column(String(20), nullable=False)
    rejection_reason = Column(Text, nullable=True)
    suggested_change = Column(Text, nullable=True)
    avoid_time = Column(String(100), nullable=True)
    additional_constraint = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    request = relationship("MaintenanceRequest", back_populates="decisions")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"), nullable=True)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, default="")
    timestamp = Column(DateTime, default=datetime.utcnow)
    request = relationship("MaintenanceRequest", back_populates="audit_logs")


class BlockExecution(Base):
    __tablename__ = "block_executions"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("block_plans.id"), unique=True, nullable=False)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"), nullable=False)
    block_id = Column(String(50), nullable=True)
    status = Column(String(30), default="SANCTIONED")
    sanctioned_by = Column(String(100), nullable=True)
    engineer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sanctioned_at = Column(DateTime, nullable=True)
    checkin_at = Column(DateTime, nullable=True)
    block_active_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    block_notice = Column(Text, default="")
    caution_order = Column(Text, default="")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LiveSimState(Base):
    __tablename__ = "live_sim_state"
    id = Column(Integer, primary_key=True)
    sim_date = Column(String(20), nullable=False)
    sim_minutes = Column(Integer, default=330)
    speed = Column(Integer, default=30)
    running = Column(String(5), default="true")
    last_tick_at = Column(DateTime, default=datetime.utcnow)
