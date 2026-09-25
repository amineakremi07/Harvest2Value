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
            "You are an expert agricultural supply chain analyst. "
            "Given an original optimization problem and a natural language "
            "'what-if' query, extract the specific constraint modifications needed.\n\n"
            "Return ONLY a JSON array of constraint objects with this schema:\n"
            '[{"type": "modify_demand"|"modify_price"|"add_storage_limit"|'
            '"remove_buyer"|"modify_transport_cost"|"add_time_constraint", '
            '"target": "buyer_id"|"field_name", '
            '"field": "max_demand_kg"|"price_per_kg"|"distance_km"|..., '
            '"new_value": <number>, "reason": "<explanation>"}]\n\n'
            "Original data: {original_data}\n"
            "What-if query: {query}"
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
