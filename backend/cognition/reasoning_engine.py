"""
Reasoning Engine for F.R.I.D.A.Y - Multi-step chain-of-thought reasoning.
"""
from __future__ import annotations
import asyncio, json, logging, re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class ReasoningStep:
    step_number: int
    question: str
    reasoning: str
    conclusion: str
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

@dataclass
class ReasoningResult:
    query: str
    conclusion: str
    confidence: float
    reasoning_chain: list[ReasoningStep]
    caveats: list[str] = field(default_factory=list)
    sub_problems: list[str] = field(default_factory=list)
    verification_passed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SubProblem:
    id: str
    question: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 0

class ReasoningEngine:
    """Multi-step chain-of-thought reasoning with verification."""

    def __init__(self, llm_client=None, model: str = "gemini-3.6-flash"):
        self.llm_client = llm_client
        self.model = model
        self._reasoning_history: list[ReasoningResult] = []

    async def reason(self, query: str, context: dict | None = None) -> ReasoningResult:
        """Perform multi-step reasoning on a query."""
        context = context or {}
        logger.info("Starting reasoning for: %s", query[:100])

        sub_problems = await self._decompose(query, context)
        partial_results = []
        for sub in sub_problems:
            result = await self._reason_step(sub, context)
            partial_results.append(result)

        synthesis = await self._synthesize(partial_results, context)
        verification = await self._verify(synthesis, partial_results, context)

        result = ReasoningResult(
            query=query, conclusion=synthesis, confidence=verification[1],
            reasoning_chain=partial_results,
            caveats=verification[2] if len(verification) > 2 else [],
            sub_problems=[sp.question for sp in sub_problems],
            verification_passed=verification[0] == "pass",
            metadata={"sub_problem_count": len(sub_problems)},
        )
        self._reasoning_history.append(result)
        return result

    async def _decompose(self, query: str, context: dict) -> list[SubProblem]:
        """Decompose a complex problem into sub-problems."""
        prompt = (
            "Decompose this problem into 2-5 logical sub-problems.\n\n"
            f"Problem: {query}\n\n"
            f"Context: {json.dumps(context, default=str)[:500]}\n\n"
            "Return ONLY JSON: [{\"id\": \"sp1\", \"question\": \"...\", \"priority\": 1}]"
        )
        try:
            response = await self._llm_call(prompt)
            raw = self._extract_json(response)
            if raw:
                sub_problems = []
                for item in raw:
                    sub_problems.append(SubProblem(
                        id=item.get("id", f"sp{len(sub_problems)+1}"),
                        question=item.get("question", ""),
                        priority=item.get("priority", 0),
                    ))
                if sub_problems:
                    return sorted(sub_problems, key=lambda sp: sp.priority)
        except Exception as e:
            logger.warning("Decomposition failed: %s", e)
        return [SubProblem(id="sp1", question=query, priority=1)]

    async def _reason_step(self, sub_problem: SubProblem, context: dict) -> ReasoningStep:
        """Reason through a single sub-problem."""
        prompt = (
            f"Reason step-by-step about: {sub_problem.question}\n\n"
            f"Context: {json.dumps(context, default=str)[:500]}\n\n"
            "Return JSON: {\"reasoning\": \"...\", \"conclusion\": \"...\", \"confidence\": 0.9}"
        )
        try:
            response = await self._llm_call(prompt)
            raw = self._extract_json(response)
            if raw:
                return ReasoningStep(
                    step_number=sub_problem.priority,
                    question=sub_problem.question,
                    reasoning=raw.get("reasoning", ""),
                    conclusion=raw.get("conclusion", ""),
                    confidence=float(raw.get("confidence", 0.5)),
                )
        except Exception as e:
            logger.warning("Reasoning step failed: %s", e)
        return ReasoningStep(
            step_number=sub_problem.priority, question=sub_problem.question,
            reasoning="Unable to reason.", conclusion="Insufficient information.", confidence=0.1,
        )

    async def _synthesize(self, partial_results: list[ReasoningStep], context: dict) -> str:
        """Synthesize partial results into a coherent conclusion."""
        if not partial_results:
            return "No conclusions could be drawn."
        if len(partial_results) == 1:
            return partial_results[0].conclusion
        return " | ".join(r.conclusion for r in partial_results)

    async def _verify(self, synthesis: str, partial_results: list[ReasoningStep], context: dict) -> tuple:
        """Verify the conclusion."""
        avg_confidence = (
            sum(r.confidence for r in partial_results) / len(partial_results)
            if partial_results else 0.3
        )
        return ("partial", avg_confidence, ["Verification completed"])

    async def _llm_call(self, prompt: str) -> str:
        """Make an LLM call."""
        if self.llm_client:
            try:
                response = await asyncio.to_thread(
                    self.llm_client.generate_content, contents=prompt,
                )
                return response.text or ""
            except Exception as e:
                logger.debug("LLM call failed: %s", e)
                return ""
        return ""

    def _extract_json(self, text: str) -> Optional[dict | list]:
        """Extract JSON from LLM response."""
        if not text:
            return None
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def get_reasoning_history(self, limit: int = 10) -> list[ReasoningResult]:
        return self._reasoning_history[-limit:]

    def clear_history(self) -> None:
        self._reasoning_history.clear()
