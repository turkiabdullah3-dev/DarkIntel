from fastapi import APIRouter, Depends, Query

from ..dependencies import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, cases_root
from ..services.evidence import list_evidence

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


@router.get("")
def evidence(case_id: str, search: str | None = Query(None, max_length=500),
             content_type: str | None = Query(None, max_length=200), source: str | None = Query(None, max_length=500),
             limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(0, ge=0),
             root=Depends(cases_root)):
    return list_evidence(root, case_id, search, content_type, source, offset, limit)
