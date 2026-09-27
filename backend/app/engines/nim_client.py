"""NVIDIA NIM REST API client for Harvest2Value.

Handles:
  - What-If constraint extraction (natural language -> structured constraints)
  - XAI explanation generation (optimization result -> farmer-friendly narrative)
"""

import os
import json
import re
from typing import Any, Dict, List

import httpx


class NIMClient:
    """Direct REST wrapper for NVIDIA NIM endpoint (meta/llama-3.1-70b-instruct)."""

    def __init__(self) -> None:
        self.nim_url = os.getenv(
            "NIM_ENDPOINT",
            "https://api.nvidia.com/v1/llm/meta/llama-3.1-70b-instruct",
        )
        self.api_key = os.getenv("NIM_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def extract_constraints(
        self,
        query: str,
        original_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Translate a natural-language What-If query into solver constraints.

        Uses function-calling style prompt to return structured JSON.
        """
        system_prompt = (
            "You are a constraint-extraction engine for an agricultural harvest "
            "allocation optimizer. Given the original optimization data and a "
            "natural-language what-if question, output the exact constraint "
            "modifications needed to answer it.\n\n"
            "Supported constraint types — use ONLY these, spelled exactly as shown:\n\n"
            "- modify_demand — change a buyer's maximum demand.\n"
            '  {"type": "modify_demand", "target": "<exact buyer id>", '
            '"field": "max_demand_kg", "new_value": <absolute number>}\n\n'
            "- modify_price — change a buyer's price per kg.\n"
            '  {"type": "modify_price", "target": "<exact buyer id>", '
            '"field": "price_per_kg", "new_value": <absolute number>}\n\n'
            "- modify_transport_cost — change a buyer's transport cost per kg per km.\n"
            '  {"type": "modify_transport_cost", "target": "<exact buyer id>", '
            '"field": "transport_cost_per_kg_per_km", "new_value": <absolute number>}\n\n'
            "- remove_buyer — remove a buyer entirely.\n"
            '  {"type": "remove_buyer", "target": "<exact buyer id>"}\n\n'
            "- add_storage_limit — change the producer's storage capacity.\n"
            '  {"type": "add_storage_limit", "target": "storage_capacity_kg", '
            '"field": "storage_capacity_kg", "new_value": <absolute number>}\n\n'
            "Rules:\n"
            "1. \"target\" for buyer-related types MUST be an exact buyer \"id\" "
            "copied verbatim from the original data. Never invent, guess, "
            "abbreviate, or partially match an id.\n"
            "2. If the query refers to a buyer that is not present in the "
            "original data, return [].\n"
            "3. If the query is ambiguous — ambiguous target, ambiguous change, "
            "could match more than one buyer — return [].\n"
            "4. If the query lacks enough information to compute a concrete "
            "new_value, return [].\n"
            "5. new_value must always be the absolute final value, never a "
            "delta, percentage, or formula. If the query states a relative or "
            "percentage change (for example \"drops by 20%\" or \"doubles\"), "
            "compute the resulting absolute number yourself from the current "
            "value in the original data.\n"
            "6. Only use the five constraint types listed above. Never output "
            "add_buyer, add_time_constraint, or any other type, even if it "
            "seems to fit the query.\n"
            "7. A single query may require more than one constraint object "
            "(for example it names two buyers); return all of them in one array.\n"
            "8. Output ONLY a raw JSON array — no markdown, no code fences, no "
            "prose before or after it. If nothing should change, output exactly: []"
        )

        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Original data: {json.dumps(original_data, indent=2)}\n\n"
                        f"What-if query: {query}"
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
            "top_p": 0.95,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.nim_url,
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()

        return self._parse_constraints(result)

    async def generate_explanation(
        self,
        result: Dict[str, Any],
        data: Dict[str, Any],
        prompt_type: str = "allocation_explanation",
    ) -> str:
        """Generate a human-readable explanation of the optimization result."""
        system_prompt = (
            "You are an agricultural economist explaining optimization results "
            "to farmers in simple, actionable language. Explain WHY the solver made "
            "these allocation decisions, what factors drove the optimal solution, "
            "and what risks to watch for. Be empathetic, use concrete numbers, "
            "and suggest actionable next steps."
        )

        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Optimization result: {json.dumps(result, indent=2)}\n\n"
                        f"Original data: {json.dumps(data, indent=2)}\n\n"
                        "Please explain these results in farmer-friendly language."
                    ),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.nim_url,
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_constraints(llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured JSON constraint list from NIM response."""
        try:
            content = llm_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return []

        # Try direct JSON parse first
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON from markdown code block
        match = re.search(r"```json\s*\n(.*?)\n```", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Last resort: find first JSON array in the text
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        return []


# Module-level singleton for FastAPI dependency injection
nim_client = NIMClient()
