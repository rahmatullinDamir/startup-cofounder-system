# Skill: Validate Request

## Task:
Classify whether a user request is relevant to startup idea generation.

## Input Format:
User text prompt (string)

## Output Format:
JSON object:
{
  "category": "STARTUP" or "NON_STARTUP",
  "confidence": 0.0-1.0,
  "reason": "Short explanation in user's language"
}

## Classification Rules:

### STARTUP (accept):
- Business ideas, startup concepts
- Product/service innovations
- Market opportunities
- Investment opportunities
- Technology in business context

### NON_STARTUP (reject):
- Greetings and small talk
- Questions about yourself
- Creative tasks (poems, jokes, stories)
- Programming/coding requests
- Homework/academic work
- Daily life questions (recipes, weather)

## Response Guidelines:
- Be concise (reason < 50 characters)
- Match user's language (Russian/English)
- Be firm but polite
- Confidence must reflect certainty
