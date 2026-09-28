"""Evaluation rubrics and criteria definitions for LLM-as-a-Judge."""

RUBRICS = {
    "faithfulness_score": {
        "name": "Faithfulness & Anti-Hallucination",
        "description": "Measures whether hazard parameters (wind, hail, rain/snow) and dwelling attributes (roof, basement, sump pump, coverage) stated in the advisory are 100% grounded in the ground truth alert and property database records without fabrication or hallucination.",
        "score_5": "Fully Grounded / Faithful: All claims about the weather event (perils, speed, size) and property (structure, endorsements) directly match ground truth. Zero hallucination or unverified extrapolation.",
        "score_4": "Minor Imprecision: Factual with minor descriptive liberties (e.g. 'damaging winds' for '90 km/h gusts') without inventing false numbers or non-existent home features.",
        "score_3": "Moderate Hallucination: Mentions a generic feature not confirmed by data (e.g. assumes an attic/yard when not specified), or minor numerical extrapolation.",
        "score_2": "Substantial Hallucination: Fabricates critical peril numbers (e.g. claims 120 km/h when alert said 90 km/h) or invents major structural features (e.g. advises checking sump pump when home has no sump pump).",
        "score_1": "Severe Hallucination / Contradiction: Completely fabricated peril metrics or directly contradicts ground truth property profile or alert text.",
        "guidelines": "Check every single factual assertion in the hazard summary, scratchpad, exposure analysis, micro-actions, and customer notifications against the provided ground truth.",
    },
    "action_relevance_score": {
        "name": "Action Relevance & Tailoring",
        "description": "Measures how well the proposed loss-mitigation micro-actions align with the specific peril threat (e.g. vehicle protection for hail, interior shelter for tornado, basement protection for rain/snow) and how appropriately they are tailored to the property's construction and policy gaps.",
        "score_5": "Exemplary Relevance & Tailoring: Actions directly address the primary loss drivers of the active peril, specifically account for the dwelling's structural vulnerabilities (e.g., asphalt shingle age, finished basement) and coverage gaps (e.g., lack of sewer backup endorsement), and are executable within the warning lead time.",
        "score_4": "High Relevance: Well-aligned with peril and dwelling, but missing minor tailoring (e.g., generic indoor shelter without noting the home has a finished basement).",
        "score_3": "Moderate Relevance: Helpful for generic bad weather, but loosely coupled to the specific peril or not tailored to the homeowner's vulnerabilities.",
        "score_2": "Low Relevance / Impractical: Actions fail to address the primary hazard threat, or propose unrealistic measures given the lead time.",
        "score_1": "Irrelevant or Inappropriate: Proposes useless, counterproductive, or dangerous actions for the actual hazard (e.g., flood prep during a dry wind event, or hazardous outdoor work).",
        "guidelines": "Evaluate whether the actions protect against the actual loss vectors of the specific peril and whether they account for the home's specific features and coverage limits.",
    },
    "clarity_score": {
        "name": "Communication Clarity & Actionability",
        "description": "Measures how clear, concise, actionable, and appropriately urgent the customer-facing communications (SMS and Push Notifications) and micro-action instructions are, ensuring they are free of insurance jargon and immediately understandable to a homeowner under stress.",
        "score_5": "Crystal Clear & Actionable: Punchy, unambiguous, urgent without causing panic, completely free of insurance jargon, and immediately tells the homeowner WHAT the threat is and WHAT to do first. SMS strictly complies with length limits and maximizes impact.",
        "score_4": "Clear & Effective: Easy to understand with minor stylistic stiffness or slightly wordy phrasing.",
        "score_3": "Adequate: Understandable, but somewhat wordy, passive, or slightly dense for a quick glance during an emergency.",
        "score_2": "Poor Clarity: Vague instructions, confusing sequencing, heavy jargon (e.g., 'endorsement riders'), or awkward phrasing.",
        "score_1": "Incomprehensible / Dangerous: Confusing, contradictory, illegible, or dangerously unclear instructions.",
        "guidelines": "Assess readability, urgency, absence of technical insurance jargon, and immediate comprehension for a homeowner receiving an alert on their mobile phone.",
    },
}
