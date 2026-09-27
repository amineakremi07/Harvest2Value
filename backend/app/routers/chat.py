import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ..models.schemas import ChatRequest, ChatResponse, OptimizeResponse
from ..engines.solver import InvalidScenarioError, solve_optimization, merge_constraints
from ..engines.nim_client import (
    NIMConfigurationError,
    NIMResponseError,
    NoScenarioChangeError,
    nim_client,
)
from .scenario import validated_scenario_data

router = APIRouter(prefix="/api/v1", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(request: ChatRequest):
    """Conversational assistant: a What-If goes through the scenario pipeline, anything else is answered from DATA/RESULT."""
    data = validated_scenario_data(request.data)

    try:
        # Constraint extraction + its validation decide whether this is a What-If.
        try:
            constraints = await nim_client.extract_constraints(request.message, data)
        except NoScenarioChangeError:
            history = [m.model_dump() for m in request.history]
            answer = await nim_client.chat(request.message, data, request.result, history)
            return ChatResponse(message=answer)

        return await _what_if_answer(constraints, data, request.result)
    except InvalidScenarioError as e:
        raise HTTPException(status_code=422, detail=f"Invalid scenario: {e}")
    except NIMConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Chat failed: {str(e)}")


async def _what_if_answer(
    constraints: List[Dict[str, Any]],
    data: Dict[str, Any],
    previous_result: Optional[Dict[str, Any]],
) -> ChatResponse:
    modified_data = merge_constraints(data, constraints)
    new_result = solve_optimization(modified_data)

    message = _describe_what_if(constraints, data, previous_result, new_result)
    summary = await _explanation_summary(new_result, modified_data)
    if summary:
        message = f"{message} {summary}"

    return ChatResponse(
        message=message,
        type="what_if",
        result=OptimizeResponse(**new_result),
        data=modified_data,
    )


async def _explanation_summary(result: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
    """Summary from generate_explanation(); the recalculated numbers stand on their own if it is unusable."""
    try:
        explanation = json.loads(await nim_client.generate_explanation(result=result, data=data))
        summary = explanation["summary"]
    except (NIMResponseError, ValueError, KeyError, TypeError) as e:
        logger.warning("What-If explanation unavailable, answering with the recalculated numbers only: %s", e)
        return None
    return summary.strip() if isinstance(summary, str) and summary.strip() else None


def _describe_what_if(
    constraints: List[Dict[str, Any]],
    data: Dict[str, Any],
    previous_result: Optional[Dict[str, Any]],
    new_result: Dict[str, Any],
) -> str:
    names = {b["id"]: b["name"] for b in data["buyers"]}
    before = previous_result or {}
    before_allocation = before.get("allocation") or {}

    changes = _join([_describe_change(c, names) for c in constraints])
    buyers = [
        _with_previous(f"{d['buyer_name']} {_fmt(d['allocated_kg'])} kg", d["allocated_kg"],
                       (before_allocation.get(buyer_id) or {}).get("allocated_kg"), " kg")
        for buyer_id, d in new_result["allocation"].items()
    ]
    stored = _with_previous(f"{_fmt(new_result['stored_kg'])} kg stored", new_result["stored_kg"],
                            before.get("stored_kg"), " kg")
    wasted = _with_previous(f"{_fmt(new_result['wasted_kg'])} kg wasted", new_result["wasted_kg"],
                            before.get("wasted_kg"), " kg")
    return (
        f"I recalculated the plan with {changes}. "
        f"New plan: {_join(buyers)}; {stored} and {wasted}."
    )


def _describe_change(c: Dict[str, Any], names: Dict[str, str]) -> str:
    ctype = c["type"]
    name = names.get(c.get("target"), c.get("target"))
    if ctype == "remove_buyer":
        return f"{name} removed"
    value = _fmt(c["new_value"])
    if ctype == "modify_demand":
        return f"{name}'s maximum demand set to {value} kg"
    if ctype == "modify_price":
        return f"{name}'s price set to {value} per kg"
    if ctype == "modify_transport_cost":
        return f"{name}'s transport cost set to {value} per kg per km"
    return f"the storage capacity set to {value} kg"


def _with_previous(text: str, new: float, old: Optional[float], unit: str) -> str:
    if old is None or float(old) == float(new):
        return text
    return f"{text} (was {_fmt(old)}{unit})"


def _fmt(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,}"


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"
