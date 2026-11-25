from .schema import Country, Features, Level, Plan, Release, Source

COUNTRY = Country(
    iso3="NPL",
    slug="nepal",
    name="Nepal",
    status="published",
    release=Release(prefix="npl", version="v1", pil_version="1.5", years=(2021, 2022, 2023, 2024, 2025), default_year=2025),
    levels=(
        Level("province", "province", "Province", "Provinces"),
        Level("district", "district", "District", "Districts"),
        Level("municipality", "municipality", "Municipality", "Municipalities"),
    ),
    national_plan=Plan("Sixteenth Plan, 2024–2028", "http://elibrary.moest.gov.np/bitstream/123456789/308/1/16.pdf"),
    plan_source_level="top",
    ai_message="Planning documents are available for AI-assisted analysis.",
    landing_meta="{units} municipalities",
    features=Features(ai=True, plan_sources=True, province_plan_sources=True),
    source=Source(
        hierarchy={"province": "Province", "district": "District", "municipality": "Municipality"},
        boundary_candidates={
            "municipality": ("Municipality", "NAM_2", "ADM2_EN", "admin2", "shapeName", "name_2", "NAME_2"),
            "district": ("District", "NAM_1", "ADM1_EN", "admin1", "name_1", "NAME_1"),
            "province": ("Province", "NAM_1", "ADM1_EN", "admin1", "name_1", "NAME_1"),
        },
        documents_subdir="Nepal",
    ),
)
