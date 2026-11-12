"""What the LLM sends back, in one small box."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMReply:
    text: str
    stop_reason: str
    response_id: str
    model: str
