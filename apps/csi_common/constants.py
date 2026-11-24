"""CSI OAPI enumerations used by the tools."""

UNITS = {
    "lb_in_F": 1, "lb_ft_F": 2, "kip_in_F": 3, "kip_ft_F": 4, "kN_mm_C": 5, "kN_m_C": 6,
    "kgf_mm_C": 7, "kgf_m_C": 8, "N_mm_C": 9, "N_m_C": 10, "Tonf_mm_C": 11, "Tonf_m_C": 12,
    "kN_cm_C": 13, "kgf_cm_C": 14, "N_cm_C": 15, "Tonf_cm_C": 16,
}
MAT_TYPES = {"Steel": 1, "Concrete": 2, "NoDesign": 3, "Aluminum": 4, "ColdFormed": 5, "Rebar": 6, "Tendon": 7}
LOAD_TYPES = {"Dead": 1, "SuperDead": 2, "Live": 3, "ReduceLive": 4, "Quake": 5, "Wind": 6,
              "Snow": 7, "Other": 8, "Temperature": 11, "RoofLive": 12, "Notional": 13}
COMBO_TYPES = {"Linear": 0, "Envelope": 1, "AbsAdd": 2, "SRSS": 3, "Range": 4}
