import csv
import io
import json

from darkintel.timeline.exporters import export_csv, export_json, export_markdown
from darkintel.timeline.models import TimelineEvent, TimelineEventType


def events():
    return [TimelineEvent.generated(case_id="CASE-2026-0001", event_type=TimelineEventType.ANALYST_NOTE,
                                    timestamp="2026-01-01T00:00:00Z", title="=CMD()",
                                    description="<script>alert(1)</script>", source="@source",
                                    object_type="domain", object_value="+example.com")]


def test_json_export():
    assert json.loads(export_json(events()))["events"][0]["event_type"] == "analyst_note"


def test_csv_export_prevents_formula_injection():
    row = list(csv.DictReader(io.StringIO(export_csv(events()))))[0]
    assert row["title"].startswith("'=")
    assert row["object_value"].startswith("'+")
    assert row["source"].startswith("'@")


def test_markdown_export_escapes_html_and_is_deterministic():
    output = export_markdown(events())
    assert "<script>" not in output and "&lt;script&gt;" in output
    assert output == export_markdown(events())
