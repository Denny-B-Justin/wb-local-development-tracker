"""Page-level content and constants (data that pages render but the data layer never touches)."""

LANDING_FEATURES = ("map", "compare", "profile", "brief")
LANDING_SHOTS = {
    "map": "assets/img/landing/feature-map.png",
    "compare": "assets/img/landing/feature-compare.png",
    "profile": "assets/img/landing/feature-profile.png",
    "brief": "assets/img/landing/feature-brief.png",
}
LANDING_PILLARS = (("prosperity", "trending-up"), ("infrastructure", "network"), ("livability", "leaf"))
WHY_POINTS = ("problem", "does", "scope")
WHY_SECTIONS = ("problem", "does", "scope", "modules")
WHY_GLANCE = (("scores", "layers"), ("drivers", "list-tree"), ("anyCountry", "earth"), ("briefs", "file-text"))

HERO_BACKGROUND = (
    "radial-gradient(ellipse 100% 80% at 50% -5%, rgba(67,69,170,0.28) 0%, transparent 65%), "
    "radial-gradient(ellipse 60% 40% at 80% 20%, rgba(100,203,214,0.12) 0%, transparent 60%), "
    "#0A0E1A"
)
INNER_HERO_BACKGROUND = "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(67,69,170,0.2) 0%, transparent 65%), #0A0E1A"

METHODOLOGY_PIPELINE = (
    ("acquire", "data-sources"),
    ("reconcile", "preprocessing"),
    ("aggregate", "preprocessing"),
    ("normalize", "preprocessing"),
    ("score", "scoring"),
)
PIL_DIAGRAM = "assets/img/methodology/pil-diagram.png"

ABOUT_NOTE_VERSION = '2026-05-23'
ABOUT_HIGHLIGHTS = {
    "ranking": "assets/img/about/3d-pil-ranking.png",
    "quadrant": "assets/img/about/2d-quadrant.png",
    "strategyAvailability": "assets/img/about/strategy-availability.png",
    "populationDistribution": "assets/img/about/population-distribution.png",
    "aiSwot": "assets/img/about/ai-swot.png",
}
ABOUT_FIGURES = {
    "sizeDistribution": "assets/img/about/size-distribution.png",
    "recommendations": "assets/img/about/ai-recommendations.png",
    "projects": "assets/img/about/project-selection.png",
}
ABOUT_REFERENCES = ('Kaiser, Kai-Alexander, Kim, Hyunseok, Mroczka, Fabienne, & Singh, Kaushiki. (2026). Public Finance Review '
 'Fundamentals: Enhancing Public Investment Development Outcomes. Washington, DC: Global Governance Practice, '
 'forthcoming.',
 'World Bank. (2025a). pim-pam.net Digital Decision Support Resources: Workplan 2026. Washington, DC: Prosperity '
 'Vertical Governance Department Public Infrastructure Investment and Asset Governance Community of Practice.',
 'World Bank. (2025b). pim-pam.net Geospatial Planning and Budgeting Platform Country Data Cube Data Catalogue. '
 'Washington, DC & Vienna, Austria: Prosperity Vertical Governance Department Public Finance and Procurement Unit.')

RESOURCE_FOLDER = 'https://drive.google.com/drive/folders/1wUbAx7svxoAI-1de5EUHzijQSiAv5Q-a?usp=sharing'
RESOURCE_FILES = ({'id': 'briefing',
  'title': 'pim-pam.net GPB LDT Briefing 2026-05-23',
  'format': 'briefing',
  'href': 'https://docs.google.com/document/d/1xGgjxpaJm6brzIMqib_zHJc7PKms11XR/edit?usp=drivesdk&rtpof=true&sd=true'},
 {'id': 'onePager',
  'title': 'GPBP LDT v1.4 one-pager',
  'format': 'onePager',
  'href': 'https://docs.google.com/document/d/1sF1cDEyQ7nAdEB5v6MZB_40Jlpl-rLAZ/edit?usp=drivesdk&rtpof=true&sd=true'},
 {'id': 'introDeck',
  'title': 'GPBP LDT v1.4 intro deck',
  'format': 'slideDeck',
  'href': 'https://docs.google.com/presentation/d/1MvANeuR3x39SgNJaD1gRFiX4DIWBpNeq/edit?usp=drivesdk&rtpof=true&sd=true'})
COUNTRY_PACKS = ({'iso3': 'SRB',
  'href': 'https://drive.google.com/drive/folders/1WIOlbm9Et6-0CdmwCtw8KAIEqLdtcJbV?usp=drive_link',
  'files': [{'id': 'srbUpdate',
             'title': 'PIM-PAM SRB SNG LIID Update 2026-06-09',
             'format': 'updateNote',
             'href': 'https://docs.google.com/document/d/134dPr5-Z4MsLMjBKVSQVGeCWvgeTQjwz/edit?usp=drivesdk&rtpof=true&sd=true'},
            {'id': 'srbVisualization',
             'title': 'LIID Serbia - Visualization and Replication',
             'format': 'notebook',
             'href': 'https://colab.research.google.com/drive/1G-9-BOJcl7_4XGJTbGGPhJb4Pi4KNnaQ'},
            {'id': 'srbMigration',
             'title': 'LIID Serbia - Migration & Jobs Creation Analyses',
             'format': 'notebook',
             'href': 'https://colab.research.google.com/drive/1G_cV3wgSVPNmknfvLNAMRw-SH5-njGNw'}]},
 {'iso3': 'ZMB',
  'href': 'https://drive.google.com/drive/folders/1bAHP-gN_0uLIIhCxhkkMBADylAvmbQdj?usp=drive_link',
  'files': [{'id': 'zmbDemos',
             'title': 'Pim-Pam.net GPBP Zambia Demos',
             'format': 'slideDeck',
             'href': 'https://docs.google.com/presentation/d/1yWxDCvVHjNd0NPjM6UMofmXHg5GEltjw1utiV5V6OEY/edit?usp=drivesdk'},
            {'id': 'zmbNotebook',
             'title': 'GPBP - LDT Zambia',
             'format': 'notebook',
             'href': 'https://colab.research.google.com/drive/1VOQu4l75pPo0R7kOON-3Y2aqT35XDtvC'},
            {'id': 'zmbAi',
             'title': 'Zambia AI demo',
             'format': 'notebook',
             'href': 'https://colab.research.google.com/drive/1ciSSFXsWdqI3TAvyrbg4upmUnaNWaXJD'},
            {'id': 'zmbOsr',
             'title': 'GPB LDT - Zambia OSR analysis',
             'format': 'notebook',
             'href': 'https://drive.google.com/file/d/18DX7cuGtZcmtet1qMurQpHri_SvNQhRp/view?usp=drive_link'}]},
 {'iso3': 'NPL',
  'href': 'https://drive.google.com/drive/folders/115tYIXw9uxTD_MFFDQYYz66sHdqf7Inx?usp=drive_link',
  'files': []})

RELEASE_TYPES = ("major", "minor", "patch", "operational")
RELEASE_TYPE_TONE = {"major": "major", "minor": "minor", "patch": "patch", "operational": "operational"}
RELEASES = ({'version': 'v2.1.0',
  'type': 'operational',
  'date': None,
  'summary': 'The Local Development Tracker as a Python Dash app on Posit Connect, reading every number from Azure '
             'Databricks Unity Catalog. Same workspace, same design.',
  'sections': [{'title': 'Platform',
                'items': ['**Databricks data layer**: scores, context values and boundaries come from Unity Catalog '
                          'tables in prd_mega.sgpbpi163 through an OAuth service principal, with parameterized SQL '
                          'only.',
                          '**Artifact cache**: data is assembled off the request path into compressed artifacts, so '
                          'pages never wait on the warehouse; a refresh endpoint and a staleness timer keep them '
                          'current.',
                          '**One URL per view** in the form ?page=<name>, with the context, view controls and compare '
                          'tray in the query string.']},
               {'title': 'Countries',
                'items': ['**Vietnam** workspace on the post-July 2025 two-level structure (provinces and communes), '
                          'with its snake_case tables and Vietnamese place names handled in search and links.',
                          '**Onboarding a country** is a registry file, its three Unity Catalog tables and a snapshot '
                          'build; see the README.']}]},
 {'version': 'v2.0.0',
  'type': 'major',
  'summary': 'A rebuild of the Local Development Tracker on one data layer and one country registry. Every country now '
             'shares the same workspace, and every number comes straight from the database.',
  'sections': [{'title': 'Country workspace',
                'items': ['New **workspace** for each country with a context bar (year and areas) that every section '
                          'follows: Map & drivers (the start page, with the national plan linked in the sidebar), '
                          'Compare, the unit list and profiles, Planning brief, and Data & trust.',
                          '**Map & drivers**: a choropleth of real boundaries with a pillar and indicator picker, and '
                          'a detail drawer that explains what moves each score against the selected area or national '
                          'average.',
                          '**Unit profiles** with score cards, national rank, score drivers, trends across releases, '
                          'the five most similar units, and the plans and data sources behind each indicator.']},
               {'title': 'Compare',
                'items': ['**Scatterplot** of any two scores, sized by population or land area, with area and national '
                          'baselines.',
                          '**Side-by-side table** for up to five units, shared across the map and profiles through the '
                          'selection tray.',
                          '**Export CSV** keeps the exact format of the previous comparison export.']},
               {'title': 'Planning brief',
                'items': ['Rebuilt **planning brief** with a setup panel, progress steps, score narrative, SWOT, '
                          'investment recommendations, plan alignment and web context.',
                          'Every claim carries **numbered citations** linking to the data, the local and national '
                          'plans, and web sources.',
                          'Briefs generated on the previous site still load instantly, without a new AI call. **Export '
                          'PDF** and Markdown download.',
                          '**Anyone can generate a brief**: no admin unlock, within hourly and daily limits that keep '
                          'AI costs in check.']},
               {'title': 'Data and platform',
                'items': ['Scores, baselines and drivers are computed from the database rather than bundled files, so '
                          'a data reload updates every page.',
                          'Invalid boundary shapes are repaired on load (Serbia stored several stacked copies of some '
                          'municipalities).',
                          'New LDT logo and GPBP Suite branding.',
                          '**French (beta)**: the interface and the Methodology, About and Resources pages in French '
                          'at /fr, with a language switcher in the top bar. Machine-translated and awaiting review; '
                          'planning briefs stay in English.']}]},
 {'version': 'v1.4.4',
  'date': '2026-06-15',
  'type': 'minor',
  'summary': 'This release polishes the GPB ecosystem presentation after the multi-country release, adds a Resources '
             'page for LDT and country materials, and applies reviewer-requested content corrections across the public '
             'pages.',
  'sections': [{'title': 'GPB ecosystem UI alignment',
                'items': ['Aligned the global header and footer with the GPB digital tools guidance, including the '
                          'dark chrome treatment, GPB Suite badge, PIM-PAM footer branding, and updated LDT logo '
                          'usage.',
                          'Reordered the primary navigation to Home, About, Methodology, Resources, and Release Notes, '
                          'and replaced the previous Countries header link with About.',
                          'Applied the GPB primary palette across the app while preserving the black header and footer '
                          'treatment requested for the digital tools shell.']},
               {'title': 'Resources page',
                'items': ['Added a Resources page to the header and footer for core LDT reference materials and '
                          'country-specific workspaces.',
                          'Linked the GPB LDT briefing, one-pager, and intro deck, plus Serbia, Zambia, and Nepal '
                          'country folders with direct links to visible country documents, demos, and notebooks.',
                          'Refined the Resources layout by removing redundant folder copy and the top-level Drive '
                          'button so the page stays focused on document cards and country packs.']},
               {'title': 'Content cleanup and corrections',
                'items': ['Removed the homepage implemented-by strip and the methodology standardization mapping block '
                          'to reduce page clutter.',
                          'Updated About page country findings to use 161 Serbia LSGs, approximately 94% Serbia '
                          'strategy coverage, approximately 97% Zambia strategy coverage, and the corrected 94% Kosovo '
                          'footnote.',
                          'Standardized GPB Suite naming across header and footer surfaces.']}]},
 {'version': 'v1.4.3',
  'date': '2026-06-13',
  'type': 'minor',
  'summary': 'This release prepares the Local Development Tracker for the next multi-country release by expanding '
             'Serbia and Zambia workspaces, strengthening the Strategy Inventory dashboard, improving country-aware AI '
             'planning support, refreshing GPB LDT branding/content, and hardening production deployment on Vercel.',
  'sections': [{'title': 'Multi-country workspaces',
                'items': ['Added live Serbia and Zambia country landing pages and analytics routes.',
                          'Standardized Nepal, Serbia, and Zambia on the same shared country landing-page layout.',
                          'Updated the homepage to report global workspace coverage across all loaded countries.',
                          'Added generated analytics fallbacks and tracing so country analytics load correctly in '
                          'production.']},
               {'title': 'Strategy inventory',
                'items': ['Added Strategy Inventory dashboards for Serbia and Zambia.',
                          'Added Supabase-backed strategy inventory storage and ingest support.',
                          'Added fallback and sample inventory data for preview resilience.',
                          'Corrected Serbia coverage and readiness logic, including the 161-LSG denominator and '
                          'Serbian-language AI-readiness handling.']},
               {'title': 'AI planning workflow',
                'items': ['Made AI planning requests country-aware for Nepal, Serbia, and Zambia.',
                          'Updated local and SNG plan context handling while preserving existing stage compatibility.',
                          'Improved graceful behavior when local plan URLs are missing.',
                          'Fixed Vercel PDF parsing issues with server-side PDF.js worker and polyfill handling.']},
               {'title': 'Branding, content, and documentation',
                'items': ['Refreshed the About page using the GPB LDT Briefing content.',
                          'Embedded GPB LDT figures, tables, and demo screenshots from the briefing document.',
                          'Updated typography to Fira Sans headings and Inter body copy.',
                          'Added the PIL diagram to the homepage and Methodology page.',
                          'Expanded Release Notes into a more specific versioned changelog inspired by the GPBP '
                          'release-notes format.']},
               {'title': 'Deployment and stability',
                'items': ['Bundled generated analytics JSON assets for Vercel.',
                          'Added tracing safeguards for analytics fallbacks used by AI routes.',
                          'Removed build-time Google font fetching from the Next.js build path.',
                          'Added regression tests for branding/content, release notes, strategy inventory, and '
                          'country-page behavior.']}]},
 {'version': 'v1.4.2',
  'date': '2026-06-12',
  'type': 'minor',
  'summary': 'This release moves the app beyond the original Nepal-only framing, enables Serbia and Zambia strategy '
             'inventory workflows, and fixes production deployment issues for generated analytics assets and PDF '
             'document parsing on Vercel.',
  'sections': [{'title': 'Strategy inventory workflows',
                'items': ['Added Strategy Inventory dashboards for Serbia and Zambia.',
                          'Backed the strategy inventory with a new Supabase table and ingest script.',
                          'Added Serbia and Zambia sample and fallback inventory data.',
                          'Corrected Serbia inventory coverage and readiness logic, including treating parsed '
                          'Serbian-language documents as AI-ready.']},
               {'title': 'Shared country experience',
                'items': ['Updated country landing pages so Nepal, Serbia, and Zambia use the same shared layout.',
                          'Added country-aware landing actions, including the Strategy Inventory button.',
                          'Made Development plan source availability collapsible by default.',
                          'Updated homepage stats to summarize all loaded country workspaces instead of Nepal only.',
                          'Removed static Nepal-only homepage framing.']},
               {'title': 'Release notes and production fixes',
                'items': ['Added Release v1.4 notes.',
                          'Fixed Vercel deployment and runtime issues for generated analytics JSON files.',
                          'Added PDF.js server-side worker and polyfill handling for Vercel AI document parsing.']}]},
 {'version': 'v1.4',
  'date': '2026-06-12',
  'type': 'major',
  'summary': 'This release turns the Local Development Tracker into a more complete multi-country workspace, adds '
             'Serbia and Zambia strategy inventory capabilities, and refreshes the public GPB LDT briefing content.',
  'sections': [{'title': 'Country workspaces and analytics',
                'items': ['Serbia and Zambia now have live country landing pages, analytics routes, generated '
                          'analytics datasets, and country-specific boundary assets.',
                          'Nepal, Serbia, and Zambia now share the same country landing-page format, including country '
                          'snapshots, administrative-level summaries, SNG metrics, and plan-source availability.',
                          'The homepage now reports global workspace coverage across all three loaded countries '
                          'instead of presenting the application as Nepal-only.']},
               {'title': 'Strategy inventory dashboard',
                'items': ['Added Serbia and Zambia Strategy Inventory pages for tracking local strategy-document '
                          'availability, publication timing, AI readiness, missing plans, and follow-up needs.',
                          'Backed the inventory workflow with a Supabase table, ingest script, country fallback JSON, '
                          'and dashboard summaries that separate LSG-level coverage from document counts.',
                          'Corrected Serbia coverage denominators to use the expected 161 LSG universe and treated '
                          'parsed Serbian-language documents as AI-ready while preserving validation blockers.']},
               {'title': 'AI planning and document context',
                'items': ['Made AI planning requests country-aware so Zambia and Serbia can load the correct national '
                          'and local/SNG plan sources instead of defaulting to Nepal.',
                          'Kept the existing province-plan AI stage name for compatibility while relabeling prompts '
                          'and UI copy around local/SNG planning context.',
                          'Improved graceful behavior when local plan URLs are unavailable, allowing score narratives '
                          'and national-plan context to continue while blocking local-plan-dependent outputs.']},
               {'title': 'Branding, content, and documentation',
                'items': ['Replaced the About page with the GPB LDT Briefing content and embedded the relevant '
                          'briefing figures, country demo panels, strategy screenshots, and tables.',
                          'Updated the app typography to use Fira Sans for headings and Inter for body text, with '
                          'appropriate fallback fonts.',
                          'Added the PIL diagram to the homepage and Methodology page to make the Prosperity, '
                          'Infrastructure, and Livability framework more visible.']},
               {'title': 'Deployment and stability fixes',
                'items': ['Bundled generated analytics JSON files so Serbia and Zambia analytics pages load correctly '
                          'on Vercel.',
                          'Added server-side PDF.js worker handling and polyfills so AI document parsing works in '
                          'Vercel functions.',
                          'Removed build-time Google font fetching from the Next.js build path and added tracing '
                          'safeguards for generated analytics assets used by AI routes.']}]},
 {'version': 'v1.3',
  'date': '2026-05-21',
  'type': 'minor',
  'summary': 'This release introduced the multi-country portal shell and prepared the app for country-specific landing '
             'pages beyond Nepal.',
  'sections': [{'title': 'Portal and navigation',
                'items': ['Reworked the homepage into a country portal with selector-based entry points for supported '
                          'countries.',
                          'Simplified header branding, navigation, and supporting page shells to match the '
                          'multi-country product structure.',
                          'Added under-construction handling for country routes that were not ready for public '
                          'analytics yet.']},
               {'title': 'Country pages and theming',
                'items': ['Tightened country landing-page copy and CTAs so each country page emphasizes analytics '
                          'access and local context.',
                          'Added persistent dark mode across the app with themed charts, improved tooltip contrast, '
                          'and hydration-safe initialization.',
                          'Adjusted country page positioning and shared page components so future countries can reuse '
                          'the same layout patterns.']}]},
 {'version': 'v1.2',
  'date': '2026-05-21',
  'type': 'minor',
  'summary': 'This release refined the AI planning brief workflow and made analytics outputs easier to inspect and '
             'interpret.',
  'sections': [{'title': 'AI workflow refinements',
                'items': ['Improved web-context output so users see clearer summaries and source lists instead of '
                          'dense per-source cards.',
                          'Made planning-alignment bullets denser and more directly tied to the selected score theme '
                          'and planning evidence.',
                          'Expanded recommendation cards with clearer implementation-risk sections and more usable '
                          'structured outputs.']},
               {'title': 'Score interpretation',
                'items': ['Updated Step 1 AI analysis charts to plot 0-100 component scores instead of raw indicator '
                          'values.',
                          'Fixed chart ranges to match score semantics so prosperity, livability, and infrastructure '
                          'comparisons are easier to read.',
                          'Shortened AI tab labels and helper text to reduce cognitive load during the staged analysis '
                          'workflow.']}]},
 {'version': 'v1.1',
  'date': '2026-05-20',
  'type': 'major',
  'summary': 'This release added the first staged AI Planning Brief workflow on top of the municipality analytics '
             'surface.',
  'sections': [{'title': 'AI Planning Brief',
                'items': ['Added staged AI routes for indicator narrative, local plan context, national plan context, '
                          'web context, planning alignment, SWOT analysis, and investment recommendations.',
                          'Wired document parsing and AI-stage caching into Supabase-backed server routes so repeated '
                          'municipality analyses can reuse prior context.',
                          'Added structured renderers for alignment, SWOT, recommendations, and web-context outputs on '
                          'the analytics route.']},
               {'title': 'Supporting content',
                'items': ['Aligned Release Notes, Methodology, and About pages with the expanded analytics-plus-AI '
                          'product direction.',
                          'Improved AI result cards so outputs are easier to scan, compare, and validate against '
                          'source evidence.']}]},
 {'version': 'v1.0',
  'date': '2026-05-18',
  'type': 'major',
  'summary': 'This release established the public Local Development Tracker analytics application.',
  'sections': [{'title': 'Core analytics',
                'items': ['Restored the reference-style application structure with Home, Methodology, Release Notes, '
                          'and About pages.',
                          'Added interactive Plotly 2D and 3D scatterplots with hover, zoom, click selection, and axis '
                          'labels.',
                          'Shipped the MapLibre choropleth view as the default municipality map experience.']},
               {'title': 'Data foundation',
                'items': ['Completed Supabase-backed score, component, municipality context, and analytics query '
                          'layers for the public app.',
                          'Connected score-driver charts, indicator metadata, and municipality summaries to the '
                          'runtime analytics dataset.']}]})

MAP_PILLARS = ("composite", "prosperity", "infrastructure", "livability")
COMPARE_SIZES = ("population", "area", "none")
COMPARE_BASELINES = ("area", "national")
COMPARE_VIEWS = ("scatter", "table")
UNIT_SORT_KEYS = ("rank", "name", "population", "area", "composite", "prosperity", "infrastructure", "livability")
UNIT_PAGE_SIZE = 100
PROFILE_TABS = ("drivers", "trend", "peers", "plans")
SCORE_THEMES = ("prosperity", "infrastructure", "livability")
BRIEF_OUTPUTS = ("narrative", "alignment", "swot", "recommendations")
INVENTORY_READINESS_BAR = {
    "AI-ready": "bg-success-accent",
    "Found / Not Parsed": "bg-ramp-3",
    "Needs Translation": "bg-highlight",
    "Needs Validation": "bg-warning-accent",
    "Missing": "bg-ink-faint",
}
