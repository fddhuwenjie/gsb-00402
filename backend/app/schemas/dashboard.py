from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_analyses: int
    completed_analyses: int
    failed_analyses: int
    total_signatures: int
    total_functions: int
    recent_risk_distribution: dict[str, int]
    language_distribution: dict[str, int]
