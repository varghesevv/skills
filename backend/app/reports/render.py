"""Turn a report result into CSV, HTML or JSON."""

import csv
import io
from datetime import datetime
from html import escape
from typing import Any

from app.reports.types import Cell, ReportResult

_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: Cell) -> Cell:
    """Stop spreadsheet programs from running text such as =HYPERLINK(...) as a formula."""
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value


def to_csv(result: ReportResult) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    several = len(result.sections) > 1
    for index, section in enumerate(result.sections):
        if index:
            writer.writerow([])
        if several:
            writer.writerow([_csv_safe(section.title)])
        writer.writerow(section.columns)
        for row in section.rows:
            writer.writerow([_csv_safe(value) for value in row])
    return out.getvalue()


def to_html(title: str, start: datetime, end: datetime, result: ReportResult) -> str:
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse;"
        "margin:1rem 0}th,td{border:1px solid #ccc;padding:.3rem .6rem;text-align:left}"
        "th{background:#f3f3f3}</style></head><body>",
        f"<h1>{escape(title)}</h1>",
        f"<p>Window (UTC): {escape(start.isoformat())} to {escape(end.isoformat())}</p>",
    ]
    for section in result.sections:
        parts.append(f"<h2>{escape(section.title)}</h2><table><thead><tr>")
        parts.extend(f"<th>{escape(column)}</th>" for column in section.columns)
        parts.append("</tr></thead><tbody>")
        for row in section.rows:
            cells = "".join(f"<td>{escape('' if v is None else str(v))}</td>" for v in row)
            parts.append(f"<tr>{cells}</tr>")
        if not section.rows:
            parts.append(f"<tr><td colspan='{len(section.columns)}'>No data</td></tr>")
        parts.append("</tbody></table>")
    parts.append("</body></html>")
    return "".join(parts)


def to_json(
    name: str, title: str, start: datetime, end: datetime, result: ReportResult
) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "row_count": result.row_count,
        "sections": [
            {"title": s.title, "columns": s.columns, "rows": s.rows} for s in result.sections
        ],
    }
