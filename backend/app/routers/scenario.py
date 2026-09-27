from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from ..models.schemas import ScenarioRequest, OptimizeResponse
from ..engines.solver import solve_optimization, merge_constraints
from ..engines.nim_client import NIMConfigurationError, nim_client

router = APIRouter(prefix="/api/v1", tags=["scenario"])


@router.post("/scenario", response_model=OptimizeResponse)
async def scenario(request: ScenarioRequest):
    """What-If endpoint: natural language -> constraint extraction -> re-optimize."""
    try:
        original_data = request.data
        query = request.query

        # 1. Extract constraints from natural language via NIM
        extracted = await nim_client.extract_constraints(query, original_data)

        # 2. Merge constraints into original data
        modified_data = merge_constraints(original_data, extracted)

        # 3. Re-run optimization
        result = solve_optimization(modified_data)
        return OptimizeResponse(**result)
    except NIMConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scenario failed: {str(e)}")
