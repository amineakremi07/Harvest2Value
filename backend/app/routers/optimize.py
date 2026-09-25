from fastapi import APIRouter, HTTPException
from ..models.schemas import OptimizeRequest, OptimizeResponse
from ..engines.solver import solve_optimization

router = APIRouter(prefix="/api/v1", tags=["optimization"])


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest):
    """Main optimization endpoint. Runs MILP solver and returns optimal allocation."""
    try:
        data = request.model_dump()
        result = solve_optimization(data)
        return OptimizeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
