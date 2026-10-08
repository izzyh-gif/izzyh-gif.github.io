"""
Indicator Registry
===================
This is the single source of truth for every indicator the dashboard can
display. Adding a new indicator later is a matter of adding one entry here —
no other code needs to change, as long as the source client for that
"source" value already exists (see data_sources/).

Each entry's shape:
{
    "id":          str   — internal id used in API calls (?indicator=<id>)
    "label":       str   — human-readable name shown in the UI
    "category":    str   — grouping used to organize the indicator picker
    "unit":        str   — unit shown on chart axes / tooltips
    "source":      "WHO" | "OWID"
    "source_code": str   — WHO indicator code OR OWID grapher slug
    "description": str   — short explanation shown as a tooltip/info text
}

WHO indicator codes were looked up via:
    https://ghoapi.azureedge.net/api/Indicator?$filter=contains(IndicatorName,'...')
OWID slugs were verified against:
    https://ourworldindata.org/grapher/<slug>.csv
"""

from __future__ import annotations

INDICATORS = [
    {
        "id": "life_expectancy",
        "label": "Life Expectancy at Birth",
        "category": "Mortality",
        "unit": "years",
        "source": "WHO",
        "source_code": "WHOSIS_000001",
        "fallback_source": "OWID",
        "fallback_source_code": "life-expectancy",
        "source_note": "Uses WHO GHO when available; falls back to OWID if the WHO gateway is unavailable.",
        "description": "Average number of years a newborn is expected to live, both sexes combined.",
    },
    {
        "id": "under5_mortality",
        "label": "Under-5 Mortality Rate",
        "category": "Mortality",
        "unit": "deaths per 1,000 live births",
        "source": "WHO",
        "source_code": "MDG_0000000007",
        "fallback_source": "OWID",
        "fallback_source_code": "child-mortality",
        "source_note": "Uses WHO GHO when available; falls back to OWID if the WHO gateway is unavailable.",
        "description": "Probability of dying before age 5, per 1,000 live births.",
    },
    {
        "id": "maternal_mortality",
        "label": "Maternal Mortality Ratio",
        "category": "Mortality",
        "unit": "deaths per 100,000 live births",
        "source": "WHO",
        "source_code": "MDG_0000000026",
        "fallback_source": "OWID",
        "fallback_source_code": "maternal-mortality",
        "source_note": "Uses WHO GHO when available; falls back to OWID if the WHO gateway is unavailable.",
        "description": "Number of maternal deaths per 100,000 live births.",
    },
    {
        "id": "dtp3_immunization",
        "label": "DTP3 Immunization Coverage",
        "category": "Immunization",
        "unit": "% of 1-year-olds",
        "source": "WHO",
        "source_code": "WHS4_100",
        "fallback_source": "OWID",
        "fallback_source_code": "share-of-children-immunized-dtp3",
        "source_note": "Uses WHO GHO when available; falls back to OWID if the WHO gateway is unavailable.",
        "description": "Share of one-year-olds who received 3 doses of diphtheria-tetanus-pertussis vaccine.",
    },
    {
        "id": "owid_life_expectancy",
        "label": "Life Expectancy (Long-run)",
        "category": "Mortality",
        "unit": "years",
        "source": "OWID",
        "source_code": "life-expectancy",
        "description": "Period life expectancy at birth, long-run historical series.",
    },
    {
        "id": "burden_of_disease",
        "label": "Burden of Disease (DALYs per 100,000)",
        "category": "Mortality",
        "unit": "age-standardized DALYs per 100,000 people",
        "source": "OWID",
        "source_code": "burden-of-disease-who",
        "description": "Estimated age-standardized disability-adjusted life years (DALYs) from all causes per 100,000 people. The OWID series is adapted from WHO data.",
    },
    {
        "id": "health_expenditure_per_capita",
        "label": "Health Expenditure per Capita",
        "category": "Economics",
        "unit": "PPP $ (current international $)",
        "source": "OWID",
        "source_code": "annual-healthcare-expenditure-per-capita",
        "description": "Current health expenditure per person, adjusted for purchasing power.",
    },
    {
        "id": "gdp_per_capita",
        "label": "GDP per Capita",
        "category": "Economics",
        "unit": "current international $",
        "source": "OWID",
        "source_code": "gdp-per-capita-worldbank",
        "description": "Gross domestic product per person, World Bank series. Useful as a comparison variable against health outcomes.",
    },
]


def get_indicator(indicator_id: str) -> dict | None:
    """Look up a single registry entry by its id. Returns None if not found."""
    for entry in INDICATORS:
        if entry["id"] == indicator_id:
            return entry
    return None


def list_indicators() -> list[dict]:
    """Return the full registry, as served by GET /api/indicators."""
    return INDICATORS
