def attach_measured_shot_indices(summary, points):
    """Attach the measured shot grid index; (0, 0) is the map-shift origin, not the sampling mean."""
    keys = ["LOT_ID", "Wafer", "fcp_x", "fcp_y"]
    work = points[keys].copy()
    for axis, die in [("x", "DieX"), ("y", "DieY")]:
        values = pd.to_numeric(points[die], errors="coerce").astype(float) if die in points else pd.Series(np.nan, index=points.index)
        pitch_col, shift_col = f"STEP_PITCH_{axis.upper()}", f"MAP_SHIFT_{axis.upper()}"
        if pitch_col in points and shift_col in points:
            pitch = pd.to_numeric(points[pitch_col], errors="coerce").astype(float)
            shift = pd.to_numeric(points[shift_col], errors="coerce").astype(float)
            center = pd.to_numeric(points[f"fcp_{axis}"], errors="coerce").astype(float)
            derived = ((center - shift) / pitch.where(pitch.gt(0))).replace([np.inf, -np.inf], np.nan)
            usable = derived.notna() & np.isclose(derived, derived.round(), rtol=0, atol=1e-5)
            conflict = values.notna() & usable & ~np.isclose(values, derived.round(), rtol=0, atol=1e-5)
            if conflict.any():
                raise ValueError(f"{die}: 실측 index와 (fcp - MAP_SHIFT) / STEP_PITCH가 다릅니다. 좌표 메타데이터를 확인하세요.")
            values = values.fillna(derived.round().where(usable))
        invalid = values.notna() & (~np.isfinite(values) | ~np.isclose(values, values.round(), rtol=0, atol=1e-5))
        if invalid.any():
            raise ValueError(f"{die}: 정수가 아닌 shot index가 있습니다. 임의로 재번호를 부여하지 않습니다.")
        work[die] = values.round().astype("Int64")
    groups = work.groupby(keys, observed=True, dropna=False, sort=False)
    conflicts = groups[["DieX", "DieY"]].nunique(dropna=True).gt(1).any(axis=1)
    if conflicts.any():
        raise ValueError("같은 LOT/wafer/shot 중심에 여러 DieX/DieY가 있습니다. 노광 이력 또는 좌표를 확인하세요.")
    mapping = groups[["DieX", "DieY"]].first().reset_index()
    result = summary.merge(mapping, on=keys, how="left", validate="1:1", indicator="_shot_match")
    if result["_shot_match"].ne("both").any() or len(result) != len(mapping):
        raise ValueError("Shot 통계의 key가 실측 point의 shot 목록과 다릅니다. 18번 summarize_values를 다시 실행하세요.")
    result = result.drop(columns="_shot_match")
    result["shot_index_status"] = np.where(result[["DieX", "DieY"]].notna().all(axis=1), "ok", "missing_geometry")
    if result["shot_index_status"].ne("ok").any():
        print("일부 shot의 DieX/DieY를 복원할 수 없습니다. 08/19 단계의 index·pitch·map shift를 확인하세요.")
    first = ["LOT_ID", "Wafer", "DieX", "DieY", "fcp_x", "fcp_y", "shot_index_status"]
    return result[first + [col for col in summary.columns if col not in first]]
