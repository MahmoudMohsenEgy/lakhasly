from explainer.interfaces import TermFormatter


def build_table_html(spec: dict, formatter: TermFormatter) -> str:
    """Build an RTL HTML table fragment from a validated spec.

    spec = {"caption"?: str, "headers": list[str], "rows": list[list[str]]}
    Caller (the tool) is responsible for validation; this assumes a well-formed spec.
    Every user string is run through the term formatter so [[term]] and math survive.
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
