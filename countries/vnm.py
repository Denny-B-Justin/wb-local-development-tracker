from .schema import Country, Features, Level, Plan, Release, Source

# Vietnam differs from the other workspaces in three ways:
# 1. The July 2025 reform abolished districts: 34 provinces/centrally-run cities
#    directly above ~3,300 communes, wards and special zones (two levels here).
# 2. Its UC tables use snake_case columns ("year", "land_area_km2", "*_pct")
#    instead of the GPBP CSV headers, so column_aliases add those spellings.
# 3. Names carry Vietnamese diacritics (Đ/đ does not decompose under NFD), which
#    services.text folds explicitly for slugs and search.
COUNTRY = Country(
    iso3="VNM",
    slug="vietnam",
    name="Vietnam",
    status="published",
    release=Release(prefix="vnm", version="v1", pil_version="1.5", years=(2021, 2022, 2023, 2024, 2025), default_year=2025),
    levels=(
        Level("province", "province", "Province", "Provinces"),
        Level("commune", "municipality", "Commune", "Communes"),
    ),
    national_plan=Plan(
        "Vision to 2035",
        "https://vietnam.gov.vn/period-20112020/industrial-development-strategy-through-2025-vision-to-2035-10054959",
    ),
    plan_source_level="top",
    ai_message="Planning documents are available for AI-assisted analysis.",
    landing_meta="{units} communes & wards",
    features=Features(ai=True, plan_sources=True, province_plan_sources=True),
    source=Source(
        hierarchy={"province": "Province", "district": "Province", "municipality": "Municipality"},
        year_candidates=("year", "Year", "release_year", "data_year"),
        boundary_candidates={
            "municipality": ("Municipality", "NAM_2", "ADM2_EN", "admin2", "shapeName", "name_2", "NAME_2"),
            "district": ("Province", "NAM_1", "ADM1_EN", "admin1", "name_1", "NAME_1"),
            "province": ("Province", "NAM_1", "ADM1_EN", "admin1", "name_1", "NAME_1"),
        },
        column_aliases={
            "Accessibility to Hospitals (%)": ("accessibility_to_hospitals_pct",),
            "Accessibility to Schools (%)": ("accessibility_to_schools_pct",),
            "Key Structures without Access to Broadband Internet (%)": ("key_structures_without_access_to_broadband_internet_pct",),
            "Average PM25 Concentration (ug/m3)": ("average_pm25_concentration_ug_per_m3",),
            "Change in Build Area (%)": ("change_in_build_area_pct",),
            "Change in Forest Area (%)": ("change_in_forest_area_pct",),
            "Road Flood Risk (%)": ("road_flood_risk_pct",),
            "Road Heatwave Risk (%)": ("road_heatwave_risk_pct",),
            "Railway Flood Risk (%)": ("railway_flood_risk_pct",),
            "Railway Heatwave Risk (%)": ("railway_heatwave_risk_pct",),
            "Total Land Area (km2)": ("land_area_km2",),
        },
        simplify_tolerance=0.0015,
        documents_subdir="Vietnam",
    ),
    map_max_zoom=12,
)
