from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from typing import Any, Dict
from ..models.schemas import OptimizeRequest, ScenarioRequest, OptimizeResponse
from ..engines.solver import InvalidScenarioError, solve_optimization, merge_constraints
from ..engines.nim_client import NIMConfigurationError, nim_client

router = APIRouter(prefix="/api/v1", tags=["scenario"])


def validated_scenario_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate farmer data the same way /optimize does, or raise a readable 422."""
    try:
        return OptimizeRequest.model_validate(data).model_dump()
    except ValidationError as e:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise HTTPException(status_code=422, detail=f"Invalid scenario data: {errors}")


@router.post("/scenario", response_model=OptimizeResponse)
async def scenario(request: ScenarioRequest):
    """What-If endpoint: natural language -> constraint extraction -> re-optimize."""
    original_data = validated_scenario_data(request.data)

    try:
        query = request.query

        # 1. Extract constraints from natural language via the LLM
        extracted = await nim_client.extract_constraints(query, original_data)

        # 2. Merge constraints into original data
        modified_data = merge_constraints(original_data, extracted)

        # 3. Re-run optimization
        result = solve_optimization(modified_data)
        return OptimizeResponse(**result)
    except InvalidScenarioError as e:
        raise HTTPException(status_code=422, detail=f"Invalid scenario: {e}")
    except NIMConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scenario failed: {str(e)}")
