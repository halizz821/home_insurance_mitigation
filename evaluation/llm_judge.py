"""Four-call LLM Judge evaluating Faithfulness, Action Relevance, Action Correctness, and Clarity with distinct system prompts."""

import json
import logging
import os
from typing import Any, Dict, List, Optional


from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from evaluation.rubrics import RUBRICS
from evaluation.state import (
    ActionCorrectnessAssessment,
    ActionRelevanceAssessment,
    ClarityAssessment,
    EvaluationJudgment,
    FaithfulnessAssessment,
)


load_dotenv()
logger = logging.getLogger(__name__)


# ============================================================================
# Dedicated System Prompts for Each Metric
# ============================================================================

FAITHFULNESS_SYSTEM_PROMPT = f"""You are a specialized Insurance Meteorological & Property Data Auditor.
Your sole responsibility is to evaluate the FAITHFULNESS and FACTUAL GROUNDING of an autonomous agent's weather hazard advisory.

Strictly assess whether every factual claim in the advisory—including hazard metrics (wind speed, hail size, rain/snow accumulation, lead time) and property attributes (dwelling type, roof age/material, basement, sump pump, policy endorsements)—is 100% grounded in the provided Ground Truth without fabrication, hallucination, or unverified speculation.

### FAITHFULNESS SCORING RUBRIC (Score 1 to 5):
- Score 5: {RUBRICS['faithfulness_score']['score_5']}
- Score 4: {RUBRICS['faithfulness_score']['score_4']}
- Score 3: {RUBRICS['faithfulness_score']['score_3']}
- Score 2: {RUBRICS['faithfulness_score']['score_2']}
- Score 1: {RUBRICS['faithfulness_score']['score_1']}

Guideline: Compare all claims against the Ground Truth. Penalize any fabricated numbers or phantom structural features. In your justification, cite exact numbers or text to justify your score.
"""

ACTION_RELEVANCE_SYSTEM_PROMPT = f"""You are a senior Property & Casualty (P&C) Loss-Prevention Engineer and Underwriter.
Your sole responsibility is to evaluate the ACTION RELEVANCE and PROPERTY TAILORING of the loss-mitigation micro-actions proposed by an autonomous agent.

Assess whether the actions directly target the primary loss drivers of the active weather peril (e.g. windborne projectiles, hail impact, snowmelt basement infiltration, interior life-safety shelter) and whether they are tailored to the dwelling's structural vulnerabilities (roof type/age, basement type) and critical policy gaps (uninsured sewer backup or overland water).

### ACTION RELEVANCE SCORING RUBRIC (Score 1 to 5):
- Score 5: {RUBRICS['action_relevance_score']['score_5']}
- Score 4: {RUBRICS['action_relevance_score']['score_4']}
- Score 3: {RUBRICS['action_relevance_score']['score_3']}
- Score 2: {RUBRICS['action_relevance_score']['score_2']}
- Score 1: {RUBRICS['action_relevance_score']['score_1']}

Guideline: Evaluate whether the actions mitigate the specific damage mechanisms of this peril and home. Note that actions avoiding dangerous ladder/roof work in high winds (>= 60 km/h) or avoiding outdoor work in tornadoes are mandatory life-safety requirements and must not be penalized.
"""

CLARITY_SYSTEM_PROMPT = f"""You are an Emergency Communications & Consumer Clarity Specialist.
Your sole responsibility is to evaluate the CLARITY, TONE, URGENCY, and JARGON-FREE NATURE of the customer notifications (SMS and Push Notifications) and micro-action statements.

Assess whether the message immediately tells a stressed homeowner WHAT the danger is and WHAT to do first. Check that the SMS is concise (<= 160 characters), urgent without inciting panic, and free of insurance legalese/jargon (e.g., avoid technical phrases like 'endorsement riders').

### CLARITY SCORING RUBRIC (Score 1 to 5):
- Score 5: {RUBRICS['clarity_score']['score_5']}
- Score 4: {RUBRICS['clarity_score']['score_4']}
- Score 3: {RUBRICS['clarity_score']['score_3']}
- Score 2: {RUBRICS['clarity_score']['score_2']}
- Score 1: {RUBRICS['clarity_score']['score_1']}

Guideline: Evaluate readability, clarity of instructions, character compliance, and absence of confusing insurance terminology under emergency conditions.
"""

ACTION_CORRECTNESS_SYSTEM_PROMPT = f"""You are a specialized Insurance Loss Mitigation Auditor.
Your sole responsibility is to evaluate:
1. Whether an autonomous agent's proposed micro-actions semantically satisfy a predefined list of MANDATORY REFERENCE ACTIONS from the golden dataset.
2. Whether any ADDITIONAL actions proposed by the agent are logical, practical, and grounded in the provided property details and full weather alert text.

### ACTION CORRECTNESS SCORING RUBRIC (Score 1 to 5):
- Score 5: {RUBRICS['action_correctness_score']['score_5']}
- Score 4: {RUBRICS['action_correctness_score']['score_4']}
- Score 3: {RUBRICS['action_correctness_score']['score_3']}
- Score 2: {RUBRICS['action_correctness_score']['score_2']}
- Score 1: {RUBRICS['action_correctness_score']['score_1']}

### EVALUATION RULES:

1. SEMANTIC MATCHING FOR MANDATORY ACTIONS:
   - Do NOT require verbatim phrasing. If the practical intent, physical mechanism, and risk-mitigation goal of a mandatory action are addressed by the agent, mark it as COVERED.
   - Match one-to-many or many-to-one: an agent action may partially or fully satisfy a mandatory action even if structured differently.

2. EVALUATING ADDITIONAL / NOVEL ACTIONS:
   - The MANDATORY REFERENCE ACTIONS list is NOT exhaustive. It represents minimum required baselines, not the only acceptable mitigations.
   - Multi-Hazard Alerts: Evaluate additional actions against ALL perils detailed in the complete alert text (e.g., secondary hazards like torrential rain, flash flooding, localized downpours, lightning, or power loss), NOT just the alert title or primary peril.
   - Logical & Sound: If an action addresses a genuine hazard stated in the alert text, aligns with the dwelling type, and is physically plausible for the property features (e.g., advising basement checks for heavy rain when a basement exists), mark it as SOUND. DO NOT penalize or classify it as illogical.
   - Illogical & Ungrounded: An action is ILLOGICAL ONLY if it:
     * Contradicts explicit property facts (e.g., cleaning gutters on a 10th-floor condo, checking a basement when no basement exists).
     * Addresses a peril with zero presence or causal connection to the alert context (e.g., freezing pipe protection during a summer heatwave).
     * Recommends physically impossible or counterproductive measures.

3. INDEPENDENCE OF SCORES:
   - Base deductions strictly on whether missed mandatory actions were primary vs. secondary, and whether additional actions are genuinely illogical per Rule 2.
   - Do not manufacture flaws in sound additional actions to justify a lower score caused by a missed mandatory action.

4. SCOPE LIMITATION:
   - Do NOT penalize for life-safety or occupational safety concerns here (e.g., ladder use, working in storms); evaluate strictly on property loss mitigation validity and semantic coverage.
"""

# ============================================================================
# LLM Judge Class
# ============================================================================

class LLMJudge:
    """Evaluates mitigation advisories across four independent metrics using dedicated LLM calls."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided or set in environment variables.")
        self.model = model
        self.llm = ChatOpenAI(model=model, temperature=0.0, api_key=self.api_key)

    def evaluate_faithfulness(
        self,
        property_context: Dict[str, Any],
        alert_context: Dict[str, Any],
        agent_advisory: Dict[str, Any],
        scratchpad: Optional[str] = None,
    ) -> FaithfulnessAssessment:
        """Call 1: Evaluates factual faithfulness and anti-hallucination."""
        user_prompt = (
            f"### GROUND TRUTH PROPERTY & POLICY:\n{json.dumps(property_context, indent=2, ensure_ascii=False)}\n\n"
            f"### GROUND TRUTH WEATHER ALERT:\n{json.dumps(alert_context, indent=2, ensure_ascii=False)}\n\n"
            f"### AGENT ADVISORY UNDER EVALUATION:\n{json.dumps(agent_advisory, indent=2, ensure_ascii=False)}\n"
        )
        if scratchpad:
            user_prompt += f"\n### AGENT DELIBERATION SCRATCHPAD:\n{scratchpad}\n"

        structured_llm = self.llm.with_structured_output(FaithfulnessAssessment)
        return structured_llm.invoke([
            SystemMessage(content=FAITHFULNESS_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

    def evaluate_action_relevance(
        self,
        property_context: Dict[str, Any],
        alert_context: Dict[str, Any],
        agent_advisory: Dict[str, Any],
    ) -> ActionRelevanceAssessment:
        """Call 2: Evaluates action relevance to peril loss drivers and property tailoring."""
        actions = agent_advisory.get("micro_actions", [])
        user_prompt = (
            f"### ACTIVE WEATHER HAZARD:\n"
            f"Alert: {alert_context.get('alert_name', '')}\n"
            f"Description: {alert_context.get('alert_text', '')}\n\n"
            f"### DWELLING SPECIFICATIONS:\n"
            f"Type: {property_context.get('dwelling_type')}\n"
            f"Roof: {property_context.get('roof_type')} ({property_context.get('roof_age_years')} years old)\n"
            f"Basement: {property_context.get('basement_type')}\n"
            f"Sump Pump: {'Yes' if property_context.get('has_sump_pump') else 'No'}\n"
            f"Backwater Valve: {'Yes' if property_context.get('has_backwater_valve') else 'No'}\n\n"
            f"### POLICY ENDORSEMENTS & GAPS:\n"
            f"Sewer Backup: {'Covered' if property_context.get('sewer_backup_endorsed') else 'UNINSURED GAP'}\n"
            f"Overland Water: {'Covered' if property_context.get('overland_water_endorsed') else 'UNINSURED GAP'}\n\n"
            f"### PROPOSED MICRO-ACTIONS:\n{json.dumps(actions, indent=2, ensure_ascii=False)}\n"
        )

        structured_llm = self.llm.with_structured_output(ActionRelevanceAssessment)
        return structured_llm.invoke([
            SystemMessage(content=ACTION_RELEVANCE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

    def evaluate_action_correctness(
        self,
        property_context: Dict[str, Any],
        alert_context: Dict[str, Any],
        mandatory_actions: List[str],
        agent_advisory: Dict[str, Any],
    ) -> ActionCorrectnessAssessment:
        """Call 3: Evaluates semantic presence of mandatory reference actions and logic of additional actions."""
        model_actions = [
            {"priority": a.get("priority"), "category": a.get("category"), "action": a.get("action"), "rationale": a.get("rationale")}
            for a in agent_advisory.get("micro_actions", [])
        ]

        user_prompt = (
            f"### DWELLING & PROPERTY CONTEXT:\n"
            f"Type: {property_context.get('dwelling_type')}\n"
            f"Roof: {property_context.get('roof_type')} ({property_context.get('roof_age_years')} years old)\n"
            f"Basement: {property_context.get('basement_type')} (Sump Pump: {'Yes' if property_context.get('has_sump_pump') else 'No'}; Backwater Valve: {'Yes' if property_context.get('has_backwater_valve') else 'No'})\n\n"
            f"### GROUND TRUTH WEATHER ALERT:\n"            
            f"alert name: {alert_context.get('alert_name')}\n"
            f"alert Text: {alert_context.get('alert_text')}\n\n"

            f"### MANDATORY REFERENCE ACTIONS (GOLDEN DATASET):\n"
            f"{json.dumps(mandatory_actions, indent=2, ensure_ascii=False)}\n\n"
            f"### AGENT PROPOSED MICRO-ACTIONS:\n"
            f"{json.dumps(model_actions, indent=2, ensure_ascii=False)}\n"
        )

        structured_llm = self.llm.with_structured_output(ActionCorrectnessAssessment)
        return structured_llm.invoke([
            SystemMessage(content=ACTION_CORRECTNESS_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

    def evaluate_clarity(
        self,
        agent_advisory: Dict[str, Any],
    ) -> ClarityAssessment:
        """Call 4: Evaluates tone, urgency, clarity, and absence of jargon."""
        channels = agent_advisory.get("channels", {})
        sms = channels.get("sms", "")
        push = channels.get("push_notification", {})

        user_prompt = (
            f"### CUSTOMER SMS DISPATCH:\n\"{sms}\" (Length: {len(sms)} characters)\n\n"
            f"### CUSTOMER PUSH NOTIFICATION:\n"
            f"Title: {push.get('title', '')}\n"
            f"Body: {push.get('body', '')}\n\n"
            f"### MICRO-ACTIONS INSTRUCTIONS:\n"
            f"{json.dumps([a.get('action') for a in agent_advisory.get('micro_actions', [])], indent=2, ensure_ascii=False)}\n"
        )

        structured_llm = self.llm.with_structured_output(ClarityAssessment)
        return structured_llm.invoke([
            SystemMessage(content=CLARITY_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

    def evaluate(
        self,
        property_context: Dict[str, Any],
        alert_context: Dict[str, Any],
        agent_advisory: Dict[str, Any],
        mandatory_actions: Optional[List[str]] = None,
        scratchpad: Optional[str] = None,
    ) -> EvaluationJudgment:
        """Executes the four distinct LLM evaluation calls and consolidates results."""
        faithfulness = self.evaluate_faithfulness(
            property_context=property_context,
            alert_context=alert_context,
            agent_advisory=agent_advisory,
            scratchpad=scratchpad,
        )

        action_relevance = self.evaluate_action_relevance(
            property_context=property_context,
            alert_context=alert_context,
            agent_advisory=agent_advisory,
        )

        action_correctness = self.evaluate_action_correctness(
            property_context=property_context,
            alert_context=alert_context,
            mandatory_actions=mandatory_actions or [],
            agent_advisory=agent_advisory,
        )

        clarity = self.evaluate_clarity(
            agent_advisory=agent_advisory,
        )

        return EvaluationJudgment(
            faithfulness_score=faithfulness.score,
            faithfulness_justification=faithfulness.justification,
            action_relevance_score=action_relevance.score,
            action_relevance_justification=action_relevance.justification,
            action_correctness_score=action_correctness.score,
            action_correctness_justification=action_correctness.justification,
            clarity_score=clarity.score,
            clarity_justification=clarity.justification,
        )

