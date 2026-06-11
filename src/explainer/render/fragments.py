from explainer.interfaces import TermFormatter


def build_table_html(spec: dict, formatter: TermFormatter) -> str:
    """Build an RTL HTML table fragment from a validated spec.

    spec = {"caption"?: str, "headers": list[str], "rows": list[list[str]]}
    Caller (the tool) is responsible for validation; this assumes a well-formed spec.
    Every user string is run through the term formatter so [[term]] and math survive.
    Cell text is NOT HTML-escaped (the agent is trusted to emit HTML-safe content),
    consistent with how section HTML and captions are handled elsewhere in the pipeline.
    """
    fmt = formatter.format
    headers = "".join(f"<th>{fmt(h)}</th>" for h in spec["headers"])
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{fmt(c)}</td>" for c in row) + "</tr>"
        for row in spec["rows"]
    )
    caption = spec.get("caption")
    figcaption = f"<figcaption>{fmt(caption)}</figcaption>" if caption else ""
    return (
        '<figure class="table-figure">'
        '<table dir="rtl">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
        f"{figcaption}"
        "</figure>"
    )


def build_timeline_html(spec: dict, formatter: TermFormatter) -> str:
    """Build a vertical RTL timeline fragment from a validated spec.

    spec = {"title"?: str, "events": list[{"label": str, "text": str, "detail"?: str}]}
    Caller (the tool) validates the spec. Strings are NOT HTML-escaped (agent-trusted),
    consistent with the rest of the rendering pipeline; they only pass the term formatter.
    """
    fmt = formatter.format
    items = []
    for ev in spec["events"]:
        detail = ev.get("detail")
        detail_html = f'<span class="tl-detail">{fmt(detail)}</span>' if detail else ""
        items.append(
            "<li>"
            f'<span class="tl-label">{fmt(ev["label"])}</span>'
            f'<span class="tl-text">{fmt(ev["text"])}</span>'
            f"{detail_html}"
            "</li>"
        )
    title = spec.get("title")
    title_html = f'<div class="timeline-title">{fmt(title)}</div>' if title else ""
    return (
        '<figure class="timeline-figure">'
        f"{title_html}"
        f'<ol class="timeline">{"".join(items)}</ol>'
        "</figure>"
    )
