"""Write configs/assumptions.yaml and configs/policies.yaml. Numbers that can be derived from downloaded files are computed
here from those files (source says which); everything else is TODO-SOURCE (value is a placeholder) and listed in HUMAN_TASKS.md."""
from __future__ import annotations

import pandas as pd
import yaml

T = "TODO-SOURCE"


def main() -> None:
    wb = pd.read_csv("data/raw/worldbank/country_level_data.csv")
    r = wb[wb.iso3c == "IND"].iloc[0]
    per_cap = r.total_msw_total_msw_generated_tons_year * 1000 / 365 / r.population_population_number_of_people
    comp = pd.read_csv("data/raw/opencity/BBMP_Bangalore_Chemical_Composition_of_Municipal_Solid_Waste.csv", header=None, names=["m", "v"]).set_index("m").v.astype(float)
    m = {"organic": comp["Vegetable"] + comp["Organic"] + comp["Grass/leaves/wood"], "paper": comp["Paper"] + comp["Cardboard"], "plastic": comp["Plastic"],
         "glass": comp["Glass"], "metal": comp["Metal"], "textile": comp["Textiles"], "rubber_leather": comp["Leather"],
         "inert_other": comp["Debris"] + comp["Battery"] + comp["Electronic item"] + comp["Biomedical"]}
    tot = float(sum(m.values()))
    m = {k: round(float(v) / tot, 4) for k, v in m.items()}
    oc = ("OpenCity BBMP 'Chemical Composition of Municipal Solid Waste' CSV (data/raw/opencity); categories grouped (organic=Vegetable+Organic+Grass/leaves/wood; "
          f"paper=Paper+Cardboard; inert_other=Debris+Battery+Electronic+Biomedical); renormalised from sum {tot:.2f} to 1")
    cfg = {
        "generation": {
            "per_capita_kg_day": {"value": round(float(per_cap), 4), "source": "World Bank What a Waste 2.0 country CSV, IND: total_msw_generated_tons_year / population / 365 (CC BY 4.0). India-wide, not Bengaluru-specific."},
            "city_tonnes_per_day": {"value": 3250, "source": "BBMP SWM overview via build guide ('about 3,000 to 3,500 tonnes a day'); midpoint, scale check only. " + T + ": confirm in site.bbmp.gov.in/documents/Overview.pdf"},
            "persons_per_building_m2": {"value": 0.03, "source": T + ": population proxy (people per m2 of OSM building footprint); replace with Census/ward population"},
            "festival_multiplier": {"value": 1.3, "source": T + ": festival-day uplift"},
            "festival_days": {"value": [1, 40, 100, 150, 200, 260, 300, 320], "source": T + ": placeholder simulation-day indices of festival days"},
        },
        "composition": {"shares": {"value": m, "source": oc},
                        "point_variation_concentration": {"value": 40.0, "source": "assumed: Dirichlet concentration for per-point variation around the BBMP shares"}},
        "segregation": {"rate": {"value": 0.5, "source": T + ": share of recyclable material arriving separated at source"}},
        "recovery": {"efficiency": {"value": {"organic": 0.8, "paper": 0.7, "plastic": 0.6, "glass": 0.7, "metal": 0.8, "textile": 0.4, "rubber_leather": 0.3, "inert_other": 0.0}, "source": T + ": per-material recovery efficiency"},
                     "price_per_kg": {"value": {"organic": 1.5, "paper": 8.0, "plastic": 15.0, "glass": 2.0, "metal": 25.0, "textile": 3.0, "rubber_leather": 2.0, "inert_other": 0.0}, "source": T + ": INR/kg material price"}},
        "bins": {"capacity_days_of_mean_generation": {"value": 2.5, "source": T + ": bin capacity expressed as days of the point's mean daily generation (real bin sizes unknown)"},
                 "points_per_ward": {"value": 60, "source": "assumed: collection points placed per ward"},
                 "initial_fill_fraction": {"value": 0.2, "source": "assumed"}},
        "costs": {"overflow_cost_inr": {"value": 500.0, "source": T + ": penalty per overflow event"},
                  "vehicle": {"value": {"capacity_kg": 3000.0, "cost_per_km": 25.0, "fixed_daily": 500.0, "count": 3}, "source": T + ": compactor fleet"}},
        "logistics": {"facility_detour_factor": {"value": 1.4, "source": T + ": road/haversine detour for legs outside the study graph"},
                      "facility_speed_kph": {"value": 25.0, "source": T + ": average speed for facility legs"}},
        "facilities": {"default_capacity_kg_day": {"value": {"wet_plant": 3000.0, "biomethanation": 800.0, "dwcc": 1500.0, "landfill": None},
                                                    "source": T + ": kg/day available to the study area at facilities with no capacity in the OpenCity plants CSV (landfill: unbounded); placeholders"},
                       "study_area_share": {"value": 0.01, "source": T + ": share of a plant's listed capacity (OpenCity plants CSV) available to the study area, as the plants serve all of Bengaluru"},
                       "max_per_kind": {"value": 2, "source": "assumed: nearest N facilities of each kind (by haversine from the depot) used by the flow model"}},
        "flow": {"streams": {"value": {"organic": ["wet_plant", "biomethanation"], "paper": ["dwcc"], "plastic": ["dwcc"], "glass": ["dwcc"], "metal": ["dwcc"],
                                       "textile": ["dwcc"], "rubber_leather": ["dwcc"], "inert_other": ["landfill"]},
                            "source": "assumed from facility types: organic -> wet processing plants / biomethanation; dry recyclables -> DWCC (dry waste collection centres); inert -> landfill"}},
        "fleet": {"trips_per_vehicle_per_day": {"value": 3, "source": "assumed: each compactor makes this many collect-and-unload trips a day; with the placeholder fleet (3 x 3000 kg) this gives ~27 t/day of hauling capacity against ~22 t/day generated, i.e. a stressed but feasible system"},
                  "service_minutes_per_stop": {"value": 3.0, "source": "assumed: bin servicing time; enters vehicle-hours only"}},
    }
    yaml.safe_dump(cfg, open("configs/assumptions.yaml", "w"), sort_keys=False, allow_unicode=True, width=200)
    pol = {"policies": {"threshold": {"threshold_fill": 0.8, "router": "ortools", "source": "guide Tier A example: collect if predicted fill tomorrow >= 80%"},
                        "overflow_only": {"router": "pyvrp", "alpha": 1.0, "beta": 0.0, "source": "2024 integrated selection-and-routing paper (arXiv 2409.13386) style: beta=0"},
                        "recovery_aware": {"router": "pyvrp", "alpha": 1.0, "beta": 1.0, "source": "guide prize formula; alpha/beta chosen on validation seeds only, never test seeds"},
                        "value_only": {"router": "pyvrp", "alpha": 0.0, "beta": 1.0, "source": "guide: alpha=0"}},
           "horizon_days": 1, "threshold_prize_inr": 100000.0}
    yaml.safe_dump(pol, open("configs/policies.yaml", "w"), sort_keys=False)
    print("per_capita", round(float(per_cap), 4), "composition", m)


if __name__ == "__main__":
    main()
