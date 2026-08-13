from fastapi import APIRouter, Depends, Query

from ..dependencies import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, cases_root
from ..services.indicators import indicator_detail, list_indicators

router = APIRouter(prefix="/cases/{case_id}/indicators", tags=["indicators"])


@router.get("")
def indicators(case_id: str, type: str | None = Query(None, max_length=32),
               search: str | None = Query(None, max_length=500), min_confidence: float = Query(0, ge=0, le=1),
               enriched: bool | None = None, limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
               offset: int = Query(0, ge=0), root=Depends(cases_root)):
    return list_indicators(root, case_id, type, search, min_confidence, enriched, offset, limit)


@router.get("/{ioc_type}/{value:path}")
def detail(case_id: str, ioc_type: str, value: str, root=Depends(cases_root)):
    if len(value) > 4_000:
        raise ValueError("indicator value exceeds limit")
    return indicator_detail(root, case_id, ioc_type, value)
