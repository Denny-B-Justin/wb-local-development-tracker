from .schema import Country, Features, Level, Plan, Release, Source

COUNTRY = Country(
    iso3="ZMB",
    slug="zambia",
    name="Zambia",
    status="published",
    release=Release(prefix="zmb", version="v1", pil_version="1.5", years=(2021, 2022, 2023, 2024, 2025), default_year=2025),
    levels=(
        Level("province", "province", "Province", "Provinces"),
        Level("district", "municipality", "District", "Districts"),
    ),
    national_plan=Plan("8th National Development Plan", "https://www.cabinet.gov.zm/newsite/wp-content/uploads/2023/12/8NDP-2022-2026.pdf"),
    public_totals={"population": 22_500_000, "areaKm2": 763_027},
    plan_source_level="local",
    ai_message="Local/SNG planning documents are available for AI-assisted analysis where source links are loaded.",
    landing_meta="Districts",
    features=Features(ai=True, plan_sources=True, strategy_inventory=True),
    source=Source(
        hierarchy={"province": "Province", "district": "Province", "municipality": "District"},
        boundary_candidates={
            "municipality": ("NAM_2", "ADM2_EN", "admin2", "shapeName", "Municipality", "name_2", "NAME_2"),
            "district": ("NAM_1", "ADM1_EN", "admin1", "District", "name_1", "NAME_1"),
            "province": ("NAM_1", "ADM1_EN", "admin1", "Province", "name_1", "NAME_1"),
        },
        documents_subdir="Zambia",
    ),
)
