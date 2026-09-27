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
from dotenv import load_dotenv


load_dotenv()


class NIMConfigurationError(RuntimeError):
    """Raised when required NVIDIA NIM configuration is unavailable."""


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
        self.nim_url = (
            os.getenv("NIM_BASE_URL")
            or os.getenv("NIM_ENDPOINT")
            or self.nim_url
        )

    @staticmethod
    def _request_headers() -> Dict[str, str]:
        api_key = os.getenv("NIM_API_KEY", "").strip()
        if not api_key:
            raise NIMConfigurationError(
                "NIM_API_KEY is not configured. Set it in the environment or a local .env file."
            )

        return {
            "Authorization": f"Bearer {api_key}",
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
                headers=self._request_headers(),
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
            "You are an agricultural economist explaining a harvest allocation "
            "optimization result to a smallholder farmer, in simple, practical "
            "language.\n\n"
            "You will be given two JSON objects: the optimization RESULT "
            "(status, total_harvest_kg, allocated_kg, stored_kg, wasted_kg, "
            "total_revenue, total_transport_cost, net_profit, and a per-buyer "
            "allocation breakdown with buyer_name/allocated_kg/unit_price/"
            "revenue/transport_cost/net_profit/distance_km) and the original "
            "DATA used to produce it (producer harvest_kg/storage_capacity_kg/"
            "shelf_life_days, crop, each buyer's max_demand_kg/price_per_kg/"
            "distance_km/transport_cost_per_kg_per_km, and logistics limits).\n\n"
            "Grounding rules:\n"
            "1. Use ONLY numbers and facts present in the RESULT and DATA "
            "below. Never invent market trends, weather, road conditions, "
            "future prices, or buyer behavior that is not in the data.\n"
            "2. If something relevant is not present in the data, say "
            "plainly that it is not available — never guess or fill the gap "
            "with a plausible-sounding external fact.\n"
            "3. Only mention a factor (price, demand limit, transport cost, "
            "storage capacity, distance, shelf life, etc.) if it is actually "
            "present in the data AND actually affected this result. Do not "
            "claim a factor caused a decision unless the numbers support it "
            "(for example, only call a buyer 'demand-limited' if its "
            "allocated_kg equals that buyer's max_demand_kg).\n\n"
            "Content rules:\n"
            "4. Explain what was allocated, to which buyers, and why, using "
            "concrete numbers from the RESULT (kg, prices, revenue, profit).\n"
            "5. Write for someone with no knowledge of optimization or linear "
            "programming — no jargon like 'solver', 'objective function', "
            "'LP', 'variables', or 'constraints'; describe the same idea in "
            "plain terms (for example: 'the plan sends the harvest to the "
            "buyers who pay the most after transport costs').\n"
            "6. Risks must be concrete and observable in RESULT/DATA only — "
            "for example unused storage or vehicle capacity, wasted_kg above "
            "zero, unmet buyer demand, heavy reliance on a single buyer, or "
            "storage/shelf-life exposure. Do not invent risks the data "
            "cannot support.\n"
            "7. Actions must be practical and follow directly from the "
            "observed result (what to watch, negotiate, or reconsider next "
            "season). Do not state unsupported external advice as fact.\n"
            "8. If a section (why, risks, or actions) has nothing meaningful "
            "and supported to say, return an empty array for it — do not "
            "pad it with generic filler.\n\n"
            "Output format — follow this exactly:\n"
            "Return ONLY a single valid JSON object and nothing else: no "
            "markdown, no ```json code fences, no introduction, no closing "
            "remarks, no text before or after the braces.\n"
            "The object must have exactly these four keys, in this shape:\n"
            '{"summary": "<string>", "why": ["<string>", ...], '
            '"risks": ["<string>", ...], "actions": ["<string>", ...]}\n'
            "\"summary\" is always a non-empty string. \"why\", \"risks\", "
            "and \"actions\" are always arrays of strings (use [] when there "
            "is nothing supported to include). Double-check that the JSON is "
            "syntactically valid — matching braces and brackets, quoted keys "
            "and strings, commas between items, no trailing commas — before "
            "responding."
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
                headers=self._request_headers(),
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
