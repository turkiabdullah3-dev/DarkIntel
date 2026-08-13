from fastapi import APIRouter, Depends, Query

from darkintel.timeline import TimelineStore

from ..dependencies import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, cases_root
from ..schemas import AnalystNoteCreate
from ..services.timeline import list_timeline

router = APIRouter(prefix="/cases/{case_id}/timeline", tags=["timeline"])


@router.get("")
def timeline(case_id: str, event_type: str | None = Query(None, max_length=64),
             object_type: str | None = Query(None, max_length=64), object: str | None = Query(None, max_length=4_000),
             source: str | None = Query(None, max_length=500), from_time: str | None = Query(None, alias="from", max_length=100),
             to_time: str | None = Query(None, alias="to", max_length=100), search: str | None = Query(None, max_length=500),
             limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(0, ge=0),
             root=Depends(cases_root)):
    return list_timeline(root, case_id, event_type, object_type, object, source, from_time, to_time,
                         search, offset, limit)


@router.post("/notes", status_code=201)
def note(case_id: str, request: AnalystNoteCreate, root=Depends(cases_root)):
    return TimelineStore(root).add_note(case_id, request.title, request.description,
                                        request.timestamp, request.tags).to_dict()
