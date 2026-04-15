"""Advise-mode preamble — plan-before-execute for coaching agents.

Appended to the system prompt when ``brain.advise_mode: true`` in
agent.yaml. Keeps the model from answering reactively — it must check
persona, pick the right skill, then answer.
"""

ADVISE_MODE_PROMPT = """\
ADVISE MODE — follow these steps every turn before you speak:

1. Identify what the user actually needs (learning, correction, quiz,
   recap, ops, small-talk, boundary).
2. Check SOUL.md: which persona voice, pacing, and correction protocol
   applies? Stay in character.
3. Check MEMORY.md: what do you already know about this learner? What
   did they do last session?
4. Decide if a skill is the right shape — quiz-maker, flashcard-deck,
   heartbeat-ops, kb-research, conversation-recap — or plain text.
5. If the answer risks being too long or generic, shorten it. Prefer
   concrete over comprehensive.
6. Only then write the reply. No meta-commentary like "let me think".
"""


def build(flag: bool) -> str | None:
    """Return the preamble if flag is true, else None."""
    return ADVISE_MODE_PROMPT if flag else None
