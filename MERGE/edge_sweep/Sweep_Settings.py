# 28번에서 저장한 설정을 prefixed CPE solver에 복원합니다.
ES_CPE_OPTIONS = dict(es_saved_settings["cpe_options"])
es_global_settings = {
    "use_virtual_chip_points": "ES_USE_VIRTUAL_CHIP_POINTS", "virtual_wafer_radius_um": "ES_VIRTUAL_WAFER_RADIUS",
    "span_tolerance": "ES_SPAN_TOLERANCE", "minimum_ridge": "ES_MINIMUM_RIDGE", "add_ridge": "ES_ADD_RIDGE",
    "max_gopt_return": "ES_MAX_GOPT_RETURN", "max_span_iter": "ES_MAX_SPAN_ITER", "cd_tol": "ES_CD_TOL",
}
for key, variable in es_global_settings.items():
    if key not in es_saved_settings:
        raise ValueError(f"28번 실행 설정에 {key}가 없습니다. 28번을 다시 저장하세요.")
    globals()[variable] = es_saved_settings[key]
ES_RIDGE_VALVE_HYPER = copy.deepcopy(es_saved_settings["ridge_valves"])
if ES_CPE_OPTIONS["span_mode"] == "OVO3_38P_HARDLIMIT":
    ES_RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT = copy.deepcopy(es_saved_settings["active_span_limits"])
else:
    ES_RK_SPAN_LIMITS_OVO3_38P_F2F = copy.deepcopy(es_saved_settings["active_span_limits"])
print("CPE 설정 복원:", ES_CPE_OPTIONS)
