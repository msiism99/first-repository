# %% 10. 제품별 wafer map: 측정 위치·반경 구간·실측 shot 경계
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from IPython.display import display, FileLink

WM_SELECT = {}  # 자동: 측정 위치가 가장 많은 wafer. 직접 지정: {"KGVM": ("LOT_ID", 11)}
WM_PITCH_OVERRIDE_UM = {}  # STEP_PITCH가 없을 때만 실제 값 지정: {"KGVM": (26000., 32000.)}
WM_POINT_SIZE = 7
WM_COLORS = ["#2166ac", "#f6a21a", "#d73027"]
WM_BANDS = [(0., 144., "R <= 144 mm"), (144., 146., "144 < R <= 146 mm"), (146., 147., "146 < R <= 147 mm")]

if not all(name in globals() for name in ["EP_SOURCES", "EP_OUTPUT_DIR", "ep_read_product"]):
    raise RuntimeError("기존 노트북의 00번 입력 설정을 먼저 실행하세요. CPE 계산 01~09번은 다시 실행할 필요 없습니다.")
(EP_OUTPUT_DIR / "plots").mkdir(parents=True, exist_ok=True)
(EP_OUTPUT_DIR / "tables").mkdir(parents=True, exist_ok=True)


def wm_geometry(raw):
    required = ["LOT_ID", "Wafer", "fcp_x", "fcp_y"]
    missing = [c for c in required if c not in raw]
    if missing:
        raise ValueError(f"Wafer map 필수 컬럼 없음: {missing}")
    columns = required + [c for c in ["coordinate_X", "coordinate_Y", "wf_x", "wf_y", "STEP_PITCH_X", "STEP_PITCH_Y"] if c in raw]
    out = raw[columns].copy()
    for col in columns[1:]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    fallback_x = out.fcp_x + out.coordinate_X if "coordinate_X" in out else pd.Series(np.nan, index=out.index)
    fallback_y = out.fcp_y + out.coordinate_Y if "coordinate_Y" in out else pd.Series(np.nan, index=out.index)
    out["map_x_um"], out["map_y_um"] = fallback_x, fallback_y
    if {"wf_x", "wf_y"}.issubset(out.columns):
        use_wafer = np.isfinite(out[["wf_x", "wf_y"]].to_numpy(float)).all(axis=1)
        out.loc[use_wafer, ["map_x_um", "map_y_um"]] = out.loc[use_wafer, ["wf_x", "wf_y"]].to_numpy()
    out["map_radius_mm"] = np.hypot(out.map_x_um, out.map_y_um)/1000
    out["_map_valid"] = out.LOT_ID.notna() & out.Wafer.notna() & np.isfinite(out[["map_x_um", "map_y_um", "fcp_x", "fcp_y"]].to_numpy(float)).all(axis=1)
    return out


def wm_choose_wafer(frame, product):
    visible = frame.loc[frame._map_valid & frame.map_radius_mm.le(147.)]
    if product in WM_SELECT:
        lot, wafer = WM_SELECT[product]
        visible = visible.loc[visible.LOT_ID.astype(str).eq(str(lot)) & visible.Wafer.eq(float(wafer))]
    if visible.empty:
        raise ValueError(f"{product}: 선택 조건의 147mm 이내 측정 위치가 없습니다.")
    unique = visible[["LOT_ID", "Wafer", "map_x_um", "map_y_um"]].drop_duplicates()
    counts = unique.groupby(["LOT_ID", "Wafer"], observed=True, sort=False).size()
    lot, wafer = counts.idxmax()
    return frame.loc[frame.LOT_ID.eq(lot) & frame.Wafer.eq(wafer)].copy(), lot, wafer


def wm_shot_pitch(wafer, product):
    if product in WM_PITCH_OVERRIDE_UM:
        pitch = np.asarray(WM_PITCH_OVERRIDE_UM[product], dtype=float)
    else:
        values = []
        for col in ["STEP_PITCH_X", "STEP_PITCH_Y"]:
            if col not in wafer:
                raise ValueError(f"{product}: {col}이 없습니다. WM_PITCH_OVERRIDE_UM에 실제 pitch(µm)를 지정하세요.")
            valid = wafer[col].dropna().to_numpy(float)
            valid = valid[np.isfinite(valid) & (valid > 0)]
            if not len(valid) or not np.allclose(valid, valid[0], rtol=1e-9, atol=.001):
                raise ValueError(f"{product}: {col}을 하나로 정할 수 없습니다. 실제 pitch를 직접 지정하세요.")
            values.append(valid[0])
        pitch = np.asarray(values)
    if pitch.shape != (2,) or not np.isfinite(pitch).all() or (pitch <= 0).any():
        raise ValueError(f"{product}: shot pitch는 양의 X/Y 두 값이어야 합니다.")
    return pitch/1000


wm_rows = []
for product_number, source in enumerate(EP_SOURCES, start=1):
    product = str(source["product"])
    raw, _, input_path, _ = ep_read_product(source)
    geometry = wm_geometry(raw)
    del raw
    wafer, lot, wafer_id = wm_choose_wafer(geometry, product)
    sx, sy = wm_shot_pitch(wafer, product)
    plotted = wafer.loc[wafer._map_valid & wafer.map_radius_mm.le(147.)].drop_duplicates(["map_x_um", "map_y_um"])
    shots = wafer.loc[wafer._map_valid, ["fcp_x", "fcp_y"]].drop_duplicates()/1000
    fig, panel = plt.subplots(figsize=(8.5, 8.5))
    wafer_outline = Circle((0, 0), 150., fill=False, edgecolor="black", linewidth=1.5, linestyle="-", zorder=5)
    panel.add_patch(wafer_outline)
    edges = set()
    for cx, cy in shots.itertuples(index=False, name=None):
        x0, x1, y0, y1 = cx-sx/2, cx+sx/2, cy-sy/2, cy+sy/2
        for a, b in [((x0,y0),(x1,y0)),((x1,y0),(x1,y1)),((x0,y1),(x1,y1)),((x0,y0),(x0,y1))]:
            edges.add(tuple(sorted((tuple(np.round(a,6)),tuple(np.round(b,6))))))
    boundaries = LineCollection(list(edges), colors="black", linewidths=.45, linestyles="solid", zorder=1)
    boundaries.set_clip_path(wafer_outline)
    panel.add_collection(boundaries)
    counts = []
    for (lo, hi, label), color in zip(WM_BANDS, WM_COLORS):
        selected = plotted.map_radius_mm.le(hi) & (plotted.map_radius_mm.ge(lo) if lo == 0 else plotted.map_radius_mm.gt(lo))
        counts.append(int(selected.sum()))
        panel.scatter(plotted.loc[selected,"map_x_um"]/1000, plotted.loc[selected,"map_y_um"]/1000, s=WM_POINT_SIZE, c=color, edgecolors="none", zorder=3, label=f"{label} (N={counts[-1]})")
    panel.add_patch(Circle((0,0),144.,fill=False,edgecolor="black",linewidth=1.1,linestyle="--",zorder=4))
    handles, labels = panel.get_legend_handles_labels()
    handles += [Line2D([0],[0],color="black",linewidth=1.5,linestyle="-"),Line2D([0],[0],color="black",linewidth=1.1,linestyle="--")]
    labels += ["Wafer R = 150 mm", "R = 144 mm"]
    panel.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.01,1.), title="Point radius / boundaries", fontsize=9)
    panel.set(xlim=(-155,155),ylim=(-155,155),xlabel="Wafer X [mm]",ylabel="Wafer Y [mm]",title=f"{product} [{str(source['axis']).upper()}]\nLOT {lot} / Wafer {wafer_id:g}")
    panel.set_aspect("equal", adjustable="box")
    panel.grid(False)
    fig.tight_layout()
    stem = f"10_Wafer_Map_Product_{product_number:02d}"
    for suffix in ["png", "pdf"]:
        fig.savefig(EP_OUTPUT_DIR / "plots" / f"{stem}.{suffix}", dpi=220, bbox_inches="tight")
    display(fig)
    plt.close(fig)
    wm_rows.append(dict(product=product, axis=source["axis"], LOT_ID=lot, Wafer=wafer_id, n_unique_points=len(plotted), n_R_le_144=counts[0], n_R_144_146=counts[1], n_R_146_147=counts[2], n_measured_shots=len(shots),
        step_pitch_x_um=sx*1000, step_pitch_y_um=sy*1000, n_invalid_coordinates=int((~wafer._map_valid).sum()), n_outside_147=int((wafer._map_valid & wafer.map_radius_mm.gt(147.)).sum()), input_file=str(input_path), png_file=str(EP_OUTPUT_DIR / "plots" / f"{stem}.png")))

wm_summary = pd.DataFrame(wm_rows)
wm_summary.to_excel(EP_OUTPUT_DIR / "10_Wafer_Map_Index.xlsx", index=False)
wm_summary.to_parquet(EP_OUTPUT_DIR / "tables" / "10_Wafer_Map_Index.parquet", index=False)
display(wm_summary)
print("Wafer map 저장:", EP_OUTPUT_DIR / "plots")
