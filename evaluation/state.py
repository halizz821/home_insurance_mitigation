"""Schemas for the four independent evaluation metrics."""

from typing import List
from pydantic import BaseModel, Field


class FaithfulnessAssessment(BaseModel):
    """Evaluation schema for faithfulness to ground truth and anti-hallucination."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating grounding in truth without hallucination")
    justification: str = Field(description="Detailed rationale citing specific factual matches or hallucinations")


class ActionRelevanceAssessment(BaseModel):
    """Evaluation schema for action relevance to peril loss drivers and property tailoring."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating peril alignment and property tailoring")
    justification: str = Field(description="Detailed rationale on whether actions target peril loss drivers and property features")


class ActionCorrectnessAssessment(BaseModel):
    """Evaluation schema measuring semantic presence of reference mandatory actions and validity of additional actions."""
    score: int = Field(ge=1, le=5, description="Score 1-5 assessing semantic coverage of mandatory actions and logic of additional actions")
    covered_mandatory_actions: List[str] = Field(
        default_factory=list,
        description="Reference mandatory actions that were semantically found in the agent's output"
    )
    missed_mandatory_actions: List[str] = Field(
        default_factory=list,
        description="Reference mandatory actions that were omitted from the agent's output"
    )
    illogical_additional_actions: List[str] = Field(
        default_factory=list,
        description="Any additional actions proposed by the agent that are illogical, ungrounded, or irrelevant for the dwelling/peril"
    )
    justification: str = Field(
        description="Detailed rationale explaining semantic matches, omissions, and any penalized illogical additional actions"
    )


class ClarityAssessment(BaseModel):
    """Evaluation schema for communication tone, urgency, clarity, and absence of jargon."""
    score: int = Field(ge=1, le=5, description="Score 1-5 evaluating tone, clarity, and urgency of SMS and Push notifications")
    justification: str = Field(description="Detailed rationale on readability and absence of insurance jargon")


class EvaluationJudgment(BaseModel):
    """Consolidated judgment object containing the four metric scores and justifications."""
    faithfulness_score: int = Field(ge=1, le=5)
    faithfulness_justification: str
    action_relevance_score: int = Field(ge=1, le=5)
    action_relevance_justification: str
    action_correctness_score: int = Field(ge=1, le=5)
    action_correctness_justification: str
    clarity_score: int = Field(ge=1, le=5)
    clarity_justification: str

