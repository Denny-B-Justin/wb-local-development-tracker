"""Design-system building blocks shared by every page."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

from dash import html

from services.i18n import Translator


def icon(name: str, cls: str = "", label: str | None = None) -> html.Span:
    props: dict[str, Any] = {"className": f"i i-{name} {cls}".strip()}
    if label:
        props.update({"role": "img", "aria-label": label})
    else:
        props["aria-hidden"] = "true"
    return html.Span(**props)


def cx(*names: Any) -> str:
    return " ".join(str(n) for n in names if n)


def link(children, href: str, cls: str = "", replace: bool = False, **props) -> html.A:
    nav = {"data-nav": "replace" if replace else "push"}
    return html.A(children, href=href, className=cls or None, **nav, **props)


def ext(children, href: str, cls: str = "", new_tab_label: str | None = None, **props) -> html.A:
    content = children if isinstance(children, list) else [children]
    if new_tab_label:
        content = [*content, html.Span(f" {new_tab_label}", className="sr-only")]
    return html.A(content, href=href, target="_blank", rel="noopener noreferrer", className=cls, **props)


def button(children, variant: str = "primary", href: str | None = None, cls: str = "", disabled: bool = False,
           external: bool = False, **props):
    classes = cx("btn", f"btn-{variant}", cls, disabled and "is-disabled")
    if href and not disabled:
        if external:
            return html.A(children, href=href, className=classes, **props)
        return link(children, href, classes, **props)
    return html.Button(children, className=classes, disabled=disabled, type="button", **props)


def badge(text, tone: str = "neutral", cls: str = "") -> html.Span:
    return html.Span(text, className=cx("badge", f"badge-{tone}", cls))


def card(children, cls: str = "", tag: Callable = html.Section, **props):
    return tag(children, className=cx("card", cls), **props)


def card_title(text, cls: str = "") -> html.H2:
    return html.H2(text, className=cx("card-title", cls))


def card_label(text, cls: str = "") -> html.Div:
    return html.Div(text, className=cx("label-caps text-muted", cls))


def page_header(title: str, subtitle: Any = None, actions: Any = None) -> html.Div:
    return html.Div(
        [
            html.Div([html.H1(title, className="page-title"), html.P(subtitle, className="page-subtitle") if subtitle else None]),
            html.Div(actions, className="page-actions") if actions else None,
        ],
        className="page-header",
    )


def score_pill(t: Translator, value: float | None, digits: int = 1):
    if value is None:
        return html.Span("–", className="text-faint")
    return html.Span(t.score(value, digits), className=cx("score-pill", "is-high" if value >= 50 else "is-low"))


def pillar_bars(rows: Iterable[tuple[str, float | None]]) -> html.Dl:
    items = []
    for label, value in rows:
        items += [
            html.Dt(label, className="pb-label"),
            html.Dd(html.Div(className="pb-fill", style={"width": f"{max(0, min(100, value))}%"}) if value is not None else None,
                    className="pb-track", **{"aria-hidden": "true"}),
            html.Dd(html.Span("–", className="text-faint") if value is None else str(round(value)), className="pb-value"),
        ]
    return html.Dl(items, className="pillar-bars")


def diverging_bars(t: Translator, rows: list[dict[str, Any]], track: int = 110, bar_height: int = 8, digits: int = 0,
                   cls: str = "") -> html.Ul:
    extent = max([10.0, *[abs(r["value"]) for r in rows if r.get("value") is not None]])
    items = []
    for row in rows:
        value = row.get("value")
        positive = value is not None and value >= 0
        bar = None
        if value not in (None, 0):
            share = min(abs(value) / extent, 1) * 50
            bar = html.Span(className=cx("db-bar", "is-pos" if positive else "is-neg"),
                            style={"left": "50%" if positive else f"{50 - share}%", "width": f"{share}%"})
        detail = row.get("detail")
        items.append(html.Li(
            [
                html.Span(row["label"], className=cx("db-label", row.get("highlight") and "is-highlight"), title=row["label"]),
                html.Span([bar, html.Span(className="db-mid")], className="db-track", style={"height": f"{bar_height}px"}, **{"aria-hidden": "true"}),
                html.Span("–" if value is None else t.delta(value, digits),
                          className=cx("db-value", value is None and "text-faint", value is not None and ("is-pos" if positive else "is-neg"))),
                html.Span(detail, className="sr-only") if detail else None,
                html.Span(detail, className="db-tip", **{"aria-hidden": "true"}) if detail else None,
            ],
            className=cx("db-row", detail and "has-tip"),
            style={"gridTemplateColumns": f"minmax(7rem, 1fr) minmax(48px, {track}px) 40px"},
        ))
    return html.Ul(items, className=cx("diverging-bars", cls))


def ramp_legend(t: Translator, label: str | None = None) -> html.Div:
    return html.Div(
        [html.Span("0"), html.Span([html.Span(className=f"ramp-swatch ramp-{i}") for i in range(1, 7)], className="ramp-swatches", **{"aria-hidden": "true"}), html.Span("100")],
        className="ramp-legend", **{"aria-label": t.t("map.legend", label=label or t.t("map.score"))},
    )


def segmented(label: str, options: list[tuple[str, str, str]], value: str, small: bool = False) -> html.Div:
    return html.Div(
        [link(text, href, cx("seg-item", option == value and "is-active"), **{"role": "radio", "aria-checked": "true" if option == value else "false"})
         for option, text, href in options],
        className=cx("segmented", small and "segmented-sm"), role="radiogroup", **{"aria-label": label},
    )


def dropdown(trigger, panel, cls: str = "", panel_cls: str = "", align: str = "start", trigger_cls: str = "", label: str | None = None):
    summary_props = {"aria-label": label} if label else {}
    return html.Details(
        [html.Summary(trigger, className=cx("dd-trigger", trigger_cls), **summary_props),
         html.Div(panel, className=cx("dd-panel", f"dd-{align}", panel_cls), role="menu")],
        className=cx("dd", cls),
    )


def menu_label(text) -> html.Div:
    return html.Div(text, className="dd-label label-caps")


def menu_separator() -> html.Div:
    return html.Div(className="dd-sep")


def menu_item(children, href: str, checked: bool = False, cls: str = "", external: bool = False, **extra) -> Any:
    classes = cx("dd-item", checked and "is-checked", cls)
    props = {"role": "menuitemradio", "aria-checked": "true" if checked else "false", **extra}
    if external:
        return html.A(children, href=href, className=classes, **props)
    return link(children, href, classes, **props)


def view_select(t: Translator, label: str, value: str, options: list[dict[str, Any]], cls: str = "") -> html.Details:
    current = next((o for o in options if o["value"] == value), None)
    items: list[Any] = []
    previous_group = None
    for option in options:
        group = option.get("group")
        if group and group != previous_group:
            items += [menu_separator(), menu_label(group)]
        previous_group = group
        items.append(menu_item(option["label"], option["href"], option["value"] == value))
    return dropdown(
        [html.Span(label, className="text-muted"), html.Span(current["label"] if current else "", className="text-ink"), icon("chevron-down", "size-3-5")],
        items, cls=cx("view-select", cls), panel_cls="w-64",
        label=t.t("context.filterValue", label=label, value=current["label"] if current else ""),
    )


_TAG = re.compile(r"<(\w+)>(.*?)</\1>|<(\w+)\s*/>", re.S)


def rich(text: str, tags: dict[str, Callable[[str], Any]]) -> list[Any]:
    parts: list[Any] = []
    position = 0
    for match in _TAG.finditer(text):
        if match.start() > position:
            parts.append(text[position:match.start()])
        name = match.group(1) or match.group(3)
        inner = match.group(2) or ""
        render = tags.get(name)
        parts.append(render(inner) if render else inner)
        position = match.end()
    if position < len(text):
        parts.append(text[position:])
    return parts


def bold_lead(text: str) -> list[Any]:
    out: list[Any] = []
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if part.startswith("**") and part.endswith("**"):
            out.append(html.Strong(part[2:-2], className="font-semibold text-ink"))
        elif part:
            out.append(part)
    return out


def widget(kind: str, config: dict[str, Any], cls: str = "", **props) -> html.Div:
    return html.Div(className=cx("ldt-widget", cls), **{"data-widget": kind, "data-config": json.dumps(config, separators=(",", ":"), ensure_ascii=False)}, **props)


def share_button(t: Translator, small: bool = True) -> html.Button:
    return html.Button(
        [icon("link-2", "share-icon"), icon("check", "share-done"), html.Span(t.t("common.shareView"), className="share-text", **{"aria-live": "polite"})],
        type="button", className=cx("btn btn-secondary js-share", small and "btn-sm"),
        **{"data-copied": t.t("common.linkCopied"), "data-label": t.t("common.shareView"), "data-prompt": t.t("common.copyLink")},
    )
