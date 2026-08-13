from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..dependencies import cases_root
from ..services.cases import case_detail, list_cases
from ..services.search import search_case

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
def cases(root=Depends(cases_root)):
    return {"items": list_cases(root)}


@router.get("/{case_id}")
def detail(case_id: str, root=Depends(cases_root)):
    return case_detail(root, case_id)


@router.get("/{case_id}/overview")
def overview(case_id: str, root=Depends(cases_root)):
    return case_detail(root, case_id)["overview"]


@router.get("/{case_id}/search")
def search(case_id: str, q: Annotated[str, Query(min_length=1, max_length=200)],
           limit: Annotated[int, Query(ge=1, le=100)] = 25, root=Depends(cases_root)):
    return search_case(root, case_id, q, limit)
