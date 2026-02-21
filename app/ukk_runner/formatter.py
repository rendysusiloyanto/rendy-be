import uuid
from datetime import datetime


def format_result(category: str, step_code: str, step_name: str, raw_result: dict, score: int = 5):
    status_bool = raw_result.get("status", False)
    if status_bool is True:
        status, earned_score = "success", score
    elif status_bool is False:
        status, earned_score = "failed", 0
    else:
        status, earned_score = "error", 0
    return {
        "id": str(uuid.uuid4()),
        "category": category,
        "step_code": step_code,
        "step_name": step_name,
        "status": status,
        "score": earned_score,
        "max_score": score,
        "message": raw_result.get("message"),
        "raw": raw_result,
        "timestamp": datetime.utcnow().isoformat(),
    }
