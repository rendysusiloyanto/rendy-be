from pydantic import BaseModel, Field


# ---- Analyze ----

class AiAnalyzeRequest(BaseModel):
    exam_result_details: list[dict] = Field(..., description="List of failed step results (category, step_code, step_name, status, message, raw)")
    config_snippets: dict[str, str] | None = Field(None, description="Optional: nginx_config, error_log, etc.")


class AiAnalyzeResponse(BaseModel):
    explanation: str
    from_cache: bool = False


# ---- Chat ----

class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class AiChatResponse(BaseModel):
    reply: str
    input_tokens: int = 0
    output_tokens: int = 0
    remaining_today: int = 0


# ---- Chat history (GET) ----

class AiChatMessageOut(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: str | None = None


class AiChatHistoryResponse(BaseModel):
    messages: list[AiChatMessageOut]


class AiChatDailyLimitResponse(BaseModel):
    """Daily chat message limit for the current user (based on premium status)."""
    limit: int = Field(..., description="Max chat messages per day (5 non-premium, 30 premium)")
    used_today: int = Field(..., description="Messages already used today")
    remaining_today: int = Field(..., description="Remaining messages today")
