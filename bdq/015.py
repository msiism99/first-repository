# 15
# ─────────────────────────────────────────────────────────────────────
# 전체 mark TROCS fitting 결과를 df_final_adi / df_final_oco에 다시 매핑
# - df_final에는 일부 test point만 있으므로, 해당되는 점에만 trocs_fit 값을 채움
# - 매칭 키: apc_hist_index_no + fcp_x + fcp_y + coordinate_X + coordinate_Y
# ─────────────────────────────────────────────────────────────────────

def _fmt2(s):
    s = pd.to_numeric(s, errors='coerce').round(2)
    return s.map(lambda v: f"{v:.2f}" if pd.notna(v) else "<NA>")

def _norm_apc(s):
    return pd.to_numeric(s, errors='coerce').astype("Int64").astype("string")

def attach_trocs_fit_to_df_final(df_final, df_allmarks, name="ADI"):
    """
    df_allmarks의 trocs_fit_all_x/y를 df_final의 실측 point에 매핑하여
    trocs_fit_x / trocs_fit_y 컬럼으로 추가한다.
    """
    if len(df_final) == 0:
        print(f"⚠️ df_final_{name.lower()}가 비어 있습니다.")
        return df_final

    if len(df_allmarks) == 0:
        print(f"⚠️ df_trocs_allmarks_{name.lower()}가 비어 있습니다.")
        df_final = df_final.copy()
        df_final["trocs_fit_x"] = np.nan
        df_final["trocs_fit_y"] = np.nan
        return df_final

    df_final_w = df_final.copy()
    df_all_w = df_allmarks.copy()

    # ── key용 타입 정리 ─────────────────────────────
    df_final_w["apc_hist_index_no"] = pd.to_numeric(df_final_w["apc_hist_index_no"], errors="coerce").astype("Int64")
    df_all_w["apc_hist_index_no"]   = pd.to_numeric(df_all_w["apc_hist_index_no"], errors="coerce").astype("Int64")

    # df_final 쪽 좌표
    df_final_w["fcp_x_key"] = _fmt2(df_final_w["fcp_x"])
    df_final_w["fcp_y_key"] = _fmt2(df_final_w["fcp_y"])
    df_final_w["coord_x_key"] = _fmt2(df_final_w["coordinate_X"])
    df_final_w["coord_y_key"] = _fmt2(df_final_w["coordinate_Y"])
    df_final_w["apc_key"] = _norm_apc(df_final_w["apc_hist_index_no"])

    # df_allmarks 쪽 좌표
    df_all_w["fcp_x_key"] = _fmt2(df_all_w["fcp_x"])
    df_all_w["fcp_y_key"] = _fmt2(df_all_w["fcp_y"])
    df_all_w["coord_x_key"] = _fmt2(df_all_w["Coordinate_X"])
    df_all_w["coord_y_key"] = _fmt2(df_all_w["Coordinate_Y"])
    df_all_w["apc_key"] = _norm_apc(df_all_w["apc_hist_index_no"])

    # ── 필요한 컬럼만 추출 ─────────────────────────
    fit_cols = [
        "apc_key", "fcp_x_key", "fcp_y_key", "coord_x_key", "coord_y_key",
        "trocs_fit_all_x", "trocs_fit_all_y"
    ]
    df_fit_map = df_all_w[fit_cols].copy()

    # 중복 방지
    df_fit_map = df_fit_map.drop_duplicates(
        subset=["apc_key", "fcp_x_key", "fcp_y_key", "coord_x_key", "coord_y_key"],
        keep="last"
    )

    # ── merge ─────────────────────────────────────
    before = len(df_final_w)

    df_final_w = df_final_w.merge(
        df_fit_map,
        on=["apc_key", "fcp_x_key", "fcp_y_key", "coord_x_key", "coord_y_key"],
        how="left",
        validate="m:1"
    )

    # 컬럼명 정리
    df_final_w["trocs_fit_x"] = df_final_w["trocs_fit_all_x"]
    df_final_w["trocs_fit_y"] = df_final_w["trocs_fit_all_y"]

    df_final_w = df_final_w.drop(columns=[
        "trocs_fit_all_x", "trocs_fit_all_y",
        "apc_key", "fcp_x_key", "fcp_y_key", "coord_x_key", "coord_y_key"
    ], errors="ignore")

    matched = df_final_w["trocs_fit_x"].notna().sum()

    print(f"✅ df_final_{name.lower()}에 TROCS fitting 매핑 완료")
    print(f"  - rows: {before}")
    print(f"  - matched rows: {matched}")
    print(f"  - match rate: {matched / before * 100:.1f}%" if before > 0 else "  - match rate: N/A")

    return df_final_w


# ── 실행 ─────────────────────────────────────────────
df_final_adi_15 = attach_trocs_fit_to_df_final(
    df_final_adi,
    df_trocs_allmarks_adi,
    name="ADI"
)

df_final_oco_15 = attach_trocs_fit_to_df_final(
    df_final_oco,
    df_trocs_allmarks_oco,
    name="OCO"
)

df_final_oco_15['raw_x'] = df_final_oco_15['X_reg_demrc'] - df_final_oco_15['psm_fit_x']
df_final_oco_15['raw_y'] = df_final_oco_15['Y_reg_demrc'] - df_final_oco_15['psm_fit_y']

# 저장
df_final_adi_15.to_excel("df_final_adi_15.xlsx", index=False)
df_final_oco_15.to_excel("df_final_oco_15.xlsx", index=False)

print("저장 완료:")
print(" - df_final_adi_15.xlsx")
print(" - df_final_oco_15.xlsx")
