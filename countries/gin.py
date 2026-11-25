from .schema import Country, Features, Level, Plan, Release, Source

# Guinea comes from the same pipeline as Vietnam (ldt_indicators_<country> /
# ldt_scores_<country>, snake_case measures, "year"), with two differences:
# 1. Names are in NAM_1 (8 regions, incl. Conakry) and NAM_2 (342 communes:
#    rural communes and urban communes, "CU ...") in all three tables, not
#    Province/Municipality. There is no prefecture column, so two levels.
# 2. No flood measures: road/railway flood scores stay empty, as in the source.
# Area resolves from "total_land_area_km2" and population from "population" via
# the catalog defaults, so no column_aliases are needed. Boundaries are WKB.
COUNTRY = Country(
    iso3="GIN",
    slug="guinea",
    name="Guinea",
    status="published",
    release=Release(prefix="gin", version="v1", pil_version="1.5", years=(2021, 2022, 2023, 2024, 2025), default_year=2025),
    levels=(
        Level("region", "province", "Region", "Regions"),
        Level("commune", "municipality", "Commune", "Communes"),
    ),
    national_plan=Plan("Guinea country strategic plan (2024–2029)", "https://executiveboard.wfp.org/es/document_download/WFP-0000158630"),
    plan_source_level="top",
    ai_message="Planning documents are available for AI-assisted analysis where source links are loaded.",
    landing_meta="{units} communes",
    features=Features(ai=True, plan_sources=True, province_plan_sources=True),
    source=Source(
        hierarchy={"province": "NAM_1", "district": "NAM_1", "municipality": "NAM_2"},
        year_candidates=("year", "Year", "release_year", "data_year"),
        boundary_candidates={
            "municipality": ("NAM_2", "ADM2_FR", "ADM2_EN", "Municipality", "shapeName"),
            "district": ("NAM_1", "ADM1_FR", "ADM1_EN", "Province"),
            "province": ("NAM_1", "ADM1_FR", "ADM1_EN", "Province"),
        },
        documents_subdir="Guinea",
    ),
)
