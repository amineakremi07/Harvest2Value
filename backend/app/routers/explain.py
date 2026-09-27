from fastapi import APIRouter, HTTPException
from ..models.schemas import ExplainRequest, ExplainResponse
from ..engines.nim_client import NIMConfigurationError, nim_client

router = APIRouter(prefix="/api/v1", tags=["explain"])


@router.post("/explain", response_model=ExplainResponse)
async def explain(request: ExplainRequest):
    """XAI endpoint: generate farmer-friendly explanation of optimization results."""
    try:
        explanation = await nim_client.generate_explanation(
            result=request.result,
            data=request.data,
            prompt_type="allocation_explanation",
        )
        return ExplainResponse(explanation=explanation)
    except NIMConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")
