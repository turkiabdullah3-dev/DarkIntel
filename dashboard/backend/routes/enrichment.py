from fastapi import APIRouter, Depends, Query

from ..dependencies import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, cases_root
from ..services.enrichment import list_enrichment

router = APIRouter(prefix="/cases/{case_id}/enrichment", tags=["enrichment"])


@router.get("")
def enrichment(case_id: str, provider: str | None = Query(None, max_length=100),
               ioc_type: str | None = Query(None, max_length=32), success: bool | None = None,
               cached: bool | None = None, limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
               offset: int = Query(0, ge=0), root=Depends(cases_root)):
    return list_enrichment(root, case_id, provider, ioc_type, success, cached, offset, limit)
