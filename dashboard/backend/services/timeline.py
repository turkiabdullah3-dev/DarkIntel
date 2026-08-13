from pathlib import Path

from darkintel.timeline import TimelineStore

from .common import case_path, paginate


def list_timeline(root: Path, case_id: str, event_type: str | None, object_type: str | None,
                  object_value: str | None, source: str | None, from_time: str | None,
                  to_time: str | None, search: str | None, offset: int, limit: int) -> dict[str, object]:
    case_path(root, case_id)
    events = TimelineStore(root).filter(case_id, event_type=event_type, object_type=object_type,
                                        object_value=object_value, source=source, from_time=from_time, to_time=to_time)
    items = [event.to_dict() for event in events]
    if search:
        needle = search.lower()
        items = [item for item in items if needle in " ".join(str(item.get(key, ""))
                                                               for key in ("title", "description", "object_value")).lower()]
    return paginate(items, offset, limit)
