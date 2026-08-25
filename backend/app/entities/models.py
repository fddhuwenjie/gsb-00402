import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum, Table
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


task_signature_association = Table(
    "task_signature_association",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("analysis_tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("signature_file_id", Integer, ForeignKey("signature_files.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tasks = relationship("AnalysisTask", back_populates="creator")


class SignatureFile(Base):
    __tablename__ = "signature_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    description = Column(Text, default="")
    rule_count = Column(Integer, default=0)
    function_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    tasks = relationship("AnalysisTask", secondary=task_signature_association, back_populates="signature_files")


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False)
    code_path = Column(String(500), nullable=False)
    # Stable project identity used for baseline comparison. For uploaded
    # projects the scan directory is a throwaway temp path, so a caller-supplied
    # key is persisted here; for on-disk scans it defaults to the code path.
    project_key = Column(String(255), nullable=False, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    creator = relationship("User", back_populates="tasks")
    signature_files = relationship("SignatureFile", secondary=task_signature_association, back_populates="tasks")
    result = relationship("AnalysisResult", back_populates="task", uselist=False, cascade="all, delete-orphan")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("analysis_tasks.id", ondelete="CASCADE"), unique=True, nullable=False)
    report_json = Column(Text, nullable=False)
    total_files_scanned = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    total_components = Column(Integer, default=0)
    risk_level = Column(String(20), default="low")
    scan_duration = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("AnalysisTask", back_populates="result")


class AnalysisBaseline(Base):
    """A saved analysis snapshot used as the reference point for future diffs."""

    __tablename__ = "analysis_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    # The completed analysis task whose report is captured as the baseline.
    task_id = Column(Integer, ForeignKey("analysis_tasks.id", ondelete="CASCADE"), nullable=False)
    # Snapshot of the identifying project context, so later analyses can be
    # validated for consistency without depending on the mutable task row.
    language = Column(String(50), nullable=False)
    code_path = Column(String(500), nullable=False)
    # Stable project identity captured from the baseline task; diffs compare by
    # this key rather than the (possibly temporary) code path.
    project_key = Column(String(255), nullable=False, index=True)
    report_json = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("AnalysisTask")
    creator = relationship("User")
    diff_reports = relationship(
        "DiffReport", back_populates="baseline", cascade="all, delete-orphan"
    )


class DiffReport(Base):
    """A computed difference between a baseline and a later analysis task."""

    __tablename__ = "diff_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    baseline_id = Column(Integer, ForeignKey("analysis_baselines.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("analysis_tasks.id", ondelete="CASCADE"), nullable=False)
    diff_json = Column(Text, nullable=False)
    total_added = Column(Integer, default=0)
    total_removed = Column(Integer, default=0)
    total_changed = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    baseline = relationship("AnalysisBaseline", back_populates="diff_reports")
    task = relationship("AnalysisTask")
    creator = relationship("User")
