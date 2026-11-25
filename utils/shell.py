"""Chrome around the pages: site header/footer, workspace top bar, sidebar and context bar."""

from __future__ import annotations

from datetime import date
from typing import Any

from dash import html

import constants
import countries
from services import state
from services.state import Request

from .components import (
    badge, cx, dropdown, ext, icon, link, menu_item, menu_label, menu_separator,
)

SITE_LINKS = (("why-ldt", "nav.why"), ("methodology", "nav.methodology"), ("resources", "nav.resources"),
              ("release-notes", "nav.releaseNotes"), ("about", "nav.about"))


def logo(cls: str = "") -> html.Img:
    return html.Img(src="assets/img/brand/ldt.svg", alt=constants.APP_NAME, className=cx("logo", cls), width=88, height=36)


def language_switcher(req: Request) -> html.Details:
    t = req.t
    items = [menu_label(t.t("language.label"))]
    for code in constants.LOCALES:
        name = [constants.LOCALE_NAMES[code]]
        if code in constants.BETA_LOCALES:
            name.append(html.Span(t.t("language.beta"), className="lang-beta"))
        items.append(menu_item(
            [html.Span(name, className=cx(code == req.lang and "font-semibold")), icon("check", "size-4 text-indigo-600") if code == req.lang else None],
            req.lang_href(code), code == req.lang, cls="justify-between gap-6 text-body", lang=code, **{"data-lang": code},
        ))
    if req.lang in constants.BETA_LOCALES:
        items.append(html.P(t.t("language.betaNote"), className="lang-note"))
    return dropdown(
        [icon("globe", "size-3-5"), req.lang, icon("chevron-down", "size-3-5")], items,
        cls="lang-switcher", align="end", label=f"{t.t('language.label')}: {constants.LOCALE_NAMES[req.lang]}",
    )


def country_switcher(req: Request) -> html.Details:
    t = req.t
    current = req.country
    section = req.page if req.page in state.WORKSPACE_PAGES and req.page != "profile" else ("municipalities" if req.page == "profile" else "map")
    label = state.localized_country(current, t)["name"] if current else t.t("landing.selectCountry")
    items = [menu_label(t.t("workspace.switchCountry") if current else label)]
    for country in countries.visible(req.preview):
        name = state.localized_country(country, t)["name"]
        is_current = current is not None and country.iso3 == current.iso3
        href = state.build({"page": section, "country": country.slug, **({"lang": req.lang} if req.lang != constants.DEFAULT_LOCALE else {})})
        items.append(menu_item(
            [html.Span(name, className=cx(is_current and "font-semibold")),
             icon("check", "size-4 text-indigo-600", t.t("workspace.current")) if is_current else None],
            href, is_current, cls="justify-between text-body",
        ))
    return dropdown(
        [label, icon("chevron-down", "size-3-5")], items, cls="country-switcher", trigger_cls="country-pill",
        label=t.t("workspace.countryMenu", country=label) if current else label,
    )


def site_nav(req: Request, cls: str = "site-nav") -> html.Nav:
    return html.Nav([link(req.t.t(key), req.site_href(page), "site-link") for page, key in SITE_LINKS], className=cls,
                    **{"aria-label": req.t.t("nav.site")})


def site_header(req: Request) -> html.Header:
    return html.Header(
        [
            link(logo("logo-lg"), req.site_href("home"), "shrink-0", **{"aria-label": req.t.t("site.home")}),
            country_switcher(req),
            html.Span(className="flex-1"),
            site_nav(req),
            language_switcher(req),
        ],
        className="site-header",
    )


def site_footer(req: Request) -> html.Footer:
    t = req.t
    return html.Footer(
        [
            html.Div([html.Div([logo("self-start"), html.P(t.t("site.footerTagline"))], className="footer-brand")], className="footer-top"),
            html.Nav([link(t.t(key), req.site_href(page), "footer-link") for page, key in SITE_LINKS], className="footer-nav", **{"aria-label": t.t("nav.footer")}),
            html.P(t.t("site.copyright", year=str(date.today().year)), className="footer-copy"),
        ],
        className="site-footer",
    )


def site_frame(req: Request, content: Any) -> html.Div:
    return html.Div([site_header(req), html.Main(content, className="site-main"), site_footer(req)], className="site-frame")


def workspace_nav(req: Request) -> list[tuple[str, str]]:
    t = req.t
    names = state.localized_country(req.country, t)
    items = [("map", t.t("workspace.sections.map")), ("compare", t.t("workspace.sections.compare")),
             ("municipalities", names["local"]["plural"]), ("brief", t.t("workspace.sections.brief")),
             ("data", t.t("workspace.sections.data"))]
    if req.country.features.strategy_inventory:
        items.append(("strategy-inventory", t.t("workspace.sections.inventory")))
    return items


def top_bar(req: Request) -> html.Header:
    t = req.t
    return html.Header(
        [
            html.Button([icon("menu", "menu-open"), icon("x", "menu-close")], type="button", className="menu-button js-menu",
                        **{"aria-label": t.t("workspace.openMenu"), "aria-controls": "workspace-sidebar", "aria-expanded": "false",
                           "data-open": t.t("workspace.openMenu"), "data-close": t.t("workspace.closeMenu")}),
            link(logo(), req.site_href("home"), "shrink-0", **{"aria-label": t.t("site.home")}),
            country_switcher(req),
            badge(t.t("common.preview"), "preview") if req.country.status == "preview" else None,
            html.Span(className="flex-1"),
            site_nav(req, "site-nav"),
            language_switcher(req),
        ],
        className="top-bar",
    )


def sidebar(req: Request, active_unit: dict[str, str] | None) -> html.Aside:
    t = req.t
    names = state.localized_country(req.country, t)
    links = []
    compare_count = len(req.compare)
    for section, label in workspace_nav(req):
        is_parent = active_unit is not None and section == "municipalities"
        is_active = (section == req.page or (section == "municipalities" and req.page == "profile")) and not is_parent
        children: list[Any] = [label]
        if section == "compare":
            children.append(html.Span([str(compare_count), html.Span(f" {t.t('workspace.selected')}", className="sr-only")],
                                      className="nav-count", **{"data-compare-count": req.country.slug, "hidden": compare_count == 0}))
        links.append(link(children, req.href(section), cx("nav-item", is_active and "is-active", is_parent and "is-parent"),
                          **({"aria-current": "page"} if is_active else {})))
        if is_parent:
            links.append(html.Span(active_unit["name"], className="nav-child", title=active_unit["name"], **{"aria-current": "page"}))
    plan = req.country.national_plan
    return html.Aside(
        html.Div(
            [
                html.Div(
                    [
                        html.Div(t.t("workspace.countryWorkspace"), className="label-caps text-muted"),
                        html.Div(names["name"], className="sb-country"),
                        html.Div(t.t("workspace.release", year=str(req.year), key=req.country.release_key(req.year)), className="sb-release"),
                    ],
                    className="px-3",
                ),
                html.Nav(links, className="sb-nav", **{"aria-label": t.t("workspace.nav", country=names["name"])}),
                html.Div(
                    [
                        html.Div(t.t("workspace.nationalPlan"), className="label-caps text-muted"),
                        ext([plan.title, icon("arrow-up-right", "sb-plan-icon", t.t("common.opensInNewTab"))], plan.url, "sb-plan"),
                    ],
                    className="sb-plan-box",
                ) if plan else None,
                html.Nav([link(t.t(key), req.site_href(page), "sb-site-link") for page, key in SITE_LINKS], className="sb-site-nav",
                         **{"aria-label": t.t("nav.site")}),
                html.Div(link([icon("arrow-left-right", "size-3-5"), t.t("workspace.switchCountry")], req.site_href("home"), "sb-switch"), className="sb-bottom"),
            ],
            className="sb-inner",
        ),
        id="workspace-sidebar",
        className="sidebar",
    )


def _filter_select(req: Request, label: str, value_label: str, active: bool, options: list[dict[str, Any]],
                   all_option: tuple[str, str] | None, clear_href: str | None, current: str | None):
    t = req.t
    items: list[Any] = []
    if all_option:
        items += [menu_item(all_option[0], all_option[1], current is None), menu_separator()]
    else:
        items.append(menu_label(label))
    for option in options:
        items.append(menu_item(
            [html.Span([html.Span(option["label"]), html.Span(option["hint"], className="dd-hint") if option.get("hint") else None], className="flex-col"),
             html.Span(option["meta"], className="dd-meta") if option.get("meta") else None],
            option["href"], option["value"] == current, cls="justify-between",
        ))
    return html.Span(
        [
            dropdown(
                [html.Span(label, className="fs-label"), html.Span(value_label, className="fs-value"), icon("chevron-down", "size-3-5")],
                items, panel_cls="w-64", trigger_cls="fs-trigger", label=t.t("context.filterValue", label=label, value=value_label),
            ),
            link(icon("x", "size-3-5"), clear_href, "fs-clear", **{"aria-label": t.t("context.clear", label=label)}) if active and clear_href else None,
        ],
        className=cx("filter-select", active and "is-active"),
    )


def context_bar(req: Request, actions: Any = None) -> html.Div:
    t = req.t
    model = req.model
    names = state.localized_country(req.country, t)
    default_year = model.default_year if model else req.country.release.default_year
    years = model.years if model else list(req.country.release.years)
    items: list[Any] = [html.Span(t.t("context.label"), className="label-caps text-muted ctx-label")]
    items.append(_filter_select(
        req, t.t("common.year"), str(req.year), req.year != default_year,
        [{"value": str(y), "label": str(y), "href": req.with_params(year=None if y == default_year else y)} for y in reversed(years)],
        None, req.with_params(year=None), str(req.year),
    ))
    level_keys = [level.key for level in req.country.filter_levels]
    if model:
        for index, level in enumerate(names["filters"]):
            parent_key = level_keys[index - 1] if index else None
            parent_slug = req.filters.get(parent_key) if parent_key else None
            nodes = model.tree[index]["nodes"]
            options = [n for n in nodes if n["parentSlug"] == parent_slug] if parent_slug else nodes
            current = req.filters.get(level["key"])
            selected = next((n for n in options if n["slug"] == current), None) if current else None
            clear_changes = {k: None for k in level_keys[index:]}
            option_items = []
            for node in options:
                changes = dict(clear_changes)
                changes[level["key"]] = node["slug"]
                hint = None
                if not parent_slug and index > 0:
                    chain = _parent_chain(model, index, node)
                    for chain_index, chain_slug in enumerate(chain):
                        changes[level_keys[chain_index]] = chain_slug
                    parent = next((p for p in model.tree[index - 1]["nodes"] if p["slug"] == node["parentSlug"]), None)
                    hint = parent["name"] if parent else None
                option_items.append({"value": node["slug"], "label": node["name"], "hint": hint, "meta": t.count(node["unitCount"]), "href": req.with_params(**changes)})
            items.append(_filter_select(
                req, level["singular"], selected["name"] if selected else t.t("common.all"), selected is not None, option_items,
                (t.t("context.allAreas", levels=level["plural"].lower()), req.with_params(**clear_changes)),
                req.with_params(**clear_changes), selected["slug"] if selected else None,
            ))
    is_default = req.year == default_year and not any(req.filters.values())
    if not is_default:
        items.append(link(t.t("common.reset"), req.with_params(year=None, **{k: None for k in level_keys}), "ctx-reset"))
    items += [
        html.Span(className="flex-1"),
        html.Span([html.Span(className="pulse-dot", **{"aria-hidden": "true"}), t.t("common.updating")], className="ctx-updating", **{"aria-live": "polite"}),
        html.Div(actions, className="ctx-actions"),
    ]
    return html.Div(items, className="context-bar", role="region", **{"aria-label": t.t("context.region")})


def _parent_chain(model, level_index: int, node: dict[str, Any]) -> list[str | None]:
    chain: list[str | None] = [None] * level_index
    parent_slug = node["parentSlug"]
    for index in range(level_index - 1, -1, -1):
        chain[index] = parent_slug
        parent = next((n for n in model.tree[index]["nodes"] if n["slug"] == parent_slug), None)
        parent_slug = parent["parentSlug"] if parent else None
    return chain


def workspace_frame(req: Request, content: Any, actions: Any = None, active_unit: dict[str, str] | None = None) -> html.Div:
    return html.Div(
        [
            top_bar(req),
            html.Div(
                [
                    html.Div(className="menu-scrim js-menu-close", **{"aria-hidden": "true"}),
                    sidebar(req, active_unit),
                    html.Main(
                        [context_bar(req, actions), html.Div(content, className="ws-content pending-content")],
                        className="ws-main",
                    ),
                ],
                className="ws-body",
            ),
        ],
        className="ws-frame",
        **{"data-country": req.country.slug},
    )
