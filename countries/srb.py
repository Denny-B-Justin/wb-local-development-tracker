from .schema import Country, Features, Level, Plan, Release, Source

COUNTRY = Country(
    iso3="SRB",
    slug="serbia",
    name="Serbia",
    status="published",
    release=Release(prefix="srb", version="v1", pil_version="1.5", years=(2021, 2022, 2023, 2024, 2025), default_year=2025),
    levels=(
        Level("district", "province", "District", "Districts"),
        Level("municipality", "municipality", "Municipality", "Municipalities"),
    ),
    national_plan=Plan("Serbia 2030 Strategy", "https://rsjp.gov.rs/wp-content/uploads/Srbija-i-Agenda-2030.-februar-2024.-lat.pdf"),
    public_totals={"population": 6_700_000},
    plan_source_level="local",
    ai_message="Local/SNG planning documents are available for AI-assisted analysis where source links are loaded.",
    landing_meta="Municipalities & cities",
    features=Features(ai=True, plan_sources=True, strategy_inventory=True, translation_check=True),
    source=Source(
        hierarchy={"province": "Province", "district": "Province", "municipality": "District"},
        boundary_candidates={
            "municipality": ("Municipality", "ADM2_EN", "admin2", "shapeName", "NAM_2", "name_2", "NAME_2"),
            "district": ("District", "ADM1_EN", "admin1", "NAM_1", "name_1", "NAME_1"),
            "province": ("District", "ADM1_EN", "admin1", "NAM_1", "name_1", "NAME_1"),
        },
        documents_subdir="Serbia",
    ),
)
