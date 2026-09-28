"""Schemas for the three independent evaluation metrics."""

from pydantic import BaseModel, Field


class FaithfulnessAssessment(BaseModel):
    """Evaluation schema for faithfulness to ground truth and anti-hallucination."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating grounding in truth without hallucination")
    justification: str = Field(description="Detailed rationale citing specific factual matches or hallucinations")


class ActionRelevanceAssessment(BaseModel):
    """Evaluation schema for action relevance to peril loss drivers and property tailoring."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating peril alignment and property tailoring")
    justification: str = Field(description="Detailed rationale on whether actions target peril loss drivers and property features")


class ClarityAssessment(BaseModel):
    """Evaluation schema for communication tone, urgency, clarity, and absence of jargon."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating tone, clarity, and urgency of SMS and Push notifications")
    justification: str = Field(description="Detailed rationale on readability and absence of insurance jargon")


class EvaluationJudgment(BaseModel):
    """Consolidated judgment object containing the three metric scores and justifications."""
    faithfulness_score: int = Field(ge=1, le=5)
    faithfulness_justification: str
    action_relevance_score: int = Field(ge=1, le=5)
    action_relevance_justification: str
    clarity_score: int = Field(ge=1, le=5)
    clarity_justification: str
