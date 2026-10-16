"""Build the standalone, editable ADI/OCO analysis notebook (not a runtime dependency)."""
import ast
import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / 'MRC_PSM_decorrect.ipynb').read_text(encoding='utf-8'))
cells = []


def md(source):
    cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': textwrap.dedent(source).strip() + '\n'})


def code(tag, source):
    source = textwrap.dedent(source).strip() + '\n'
    compile(source, tag, 'exec')
    assert len(source.splitlines()) < 1000, tag
    cells.append({'cell_type': 'code', 'metadata': {'tags': [tag]}, 'execution_count': None, 'outputs': [], 'source': source})


def source_objects(names):
    result = {}
    for cell in SOURCE['cells']:
        if cell['cell_type'] != 'code':
            continue
        for node in ast.parse(cell['source']).body:
            name = getattr(node, 'name', None)
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            if name in names:
                result[name] = ast.get_source_segment(cell['source'], node)
    return '\n\n'.join(result[name] for name in names)


md(r'''
# ADI/OCO wafer별 상관 분석
이 파일을 **`C:\PHOTO_ANALYSIS\BASIC\ADI_OCO_Correlation.ipynb`**에 놓고 위에서 아래로 실행합니다. DB 조회 없이 기존 `output_decorrect_notebook\stages`의 Parquet/전체 Excel을 읽습니다. 결과는 새 `output_adi_oco_correlation` 폴더에 저장합니다.

**확정한 데이터 기준은 ADI=`raw_x/raw_y`, OCO=`X_reg/Y_reg`입니다.** 현재 실제 오차 기준의 분석과 OCO 시뮬레이션은 **14~19번**이며 `output_oco_adi_raw_optimized`에 따로 저장합니다. 기본 분석 방향은 X입니다. 00~13번의 Reg 비교는 계측 출력에 대한 참고 결과이고, 06~09번은 기존 ΔK 방식의 ADI 시뮬레이션으로 별도 보존합니다.

1. **Reg ↔ Reg:** 같은 wafer의 X/Y mean, 3σ를 비교합니다.
2. **ADI ideal 보정 simulation ↔ OCO real_residual:** 기적용 K−ideal K → ADI point별 보정 차이 → 기존 Reg−보정 차이 순서로 계산합니다.
3. **Reg에서 추출한 WK/RK ↔ WK/RK:** ADI/OCO Reg에서 각각 wafer 회귀를 새로 수행하고 공통 ADI 좌표에서 term 기여량을 nm로 환산합니다.

ADI는 E1, OCO는 기존 선정된 E2를 포함한 **저장된 전체 행**을 사용합니다. GROUP·공통 shot·point 1:1 필터를 추가하지 않습니다. raw 통계끼리의 상관과 rework 판정은 계산하지 않습니다.

ideal K는 기존 21번 wafer raw WK/RK 계수와 27번 shot CPE38 계수를 재사용합니다. 저장 당시 ridge/G-opt/span 제약의 결과를 그대로 사용하며 이 노트북에서 CPE를 재회귀하지 않습니다. 기존 CPE 설정을 바꾸려면 원래 노트북의 21/27 계수 파일을 갱신한 뒤 다시 실행하세요.

PSM은 **X 21항 + Y 17항의 CPE38만 변경**합니다. DB 조회에 K1~72 컬럼이 있어도 나머지 항의 ΔK는 0(변경 없음)입니다. 지원 외 항의 비영 값은 별도 진단에 남깁니다.

원단위는 측정값 µm, 좌표 µm이며 출력 통계는 nm입니다. 기본 K 그래프는 `K × max(abs(basis)) × 1000`으로 부호를 유지합니다. 실제 signed 최대값 `max_nm`, 최소값 `min_nm`, 절대최대값 `peak_abs_nm`도 모두 저장하며 00에서 그래프 기준을 변경할 수 있습니다.
''')
md('''## 00. 경로·비교 설정
표본 표준편차(ddof=1)의 3배를 3σ로 사용합니다. 실제 측정 위치가 다른 두 데이터는 wafer ID로만 연결합니다. 값이 거의 일정한 통계는 상관계수를 NaN으로 표시해 반올림 오차의 상관을 피합니다.''')
code('settings', r'''
from pathlib import Path
from typing import Sequence, Tuple
import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr
from IPython.display import display, FileLink, Image as NotebookImage

BASE_DIR = Path(r"C:\PHOTO_ANALYSIS\BASIC")
STAGE_DIR = BASE_DIR / "output_decorrect_notebook" / "stages"
OUTPUT_DIR = BASE_DIR / "output_adi_oco_correlation"
PAIR_KEYS = ["LOT_ID", "Wafer", "photo_transn_seq"]
UM_TO_NM = 1000.0
STD_DDOF = 1
MIN_CORR_WAFERS = 3
CORR_MIN_RANGE_NM = 1e-6
WK_RK_MIN_POINTS = 19
K_REFERENCE = "ADI"  # "ADI" 또는 "OCO"; 두 계수 모두 동일 reference에서 평가
K_PLOT_VALUE = "signed_peak_nm"  # "max_nm", "peak_abs_nm"도 선택 가능
EXCLUDE_RANK_DEFICIENT_K = True
SAVE_EXCEL = True
EXCEL_MAX_ROWS = 10000  # 초과하면 Excel sample + 전체 Parquet/CSV 저장
PREVIEW_ROWS = 8
SHOW_PLOTS = True
PLOT_DPI = 170
COORD_COLS = ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]
ANALYSIS_AXES = ["x"]  # 14~19번 실제 오차 분석. Y도 필요하면 ["x", "y"]

INPUT_STEMS = {
    "ADI": "15_ADI_FINAL", "OCO": "15_OCO_FINAL",
    "OCO_RESIDUAL": "27_OCO_FINAL_POINTS", "ADI_RESIDUAL": "27_ADI_FINAL_POINTS",
    "APPLIED_MRC": "09_MRC_ADI_INPUT", "APPLIED_PSM": "12_PSM_INPUT",
    "RAW_WK": "21_ADI_WK_WAFER_COEFFICIENTS", "RAW_RK": "21_ADI_RK_WAFER_COEFFICIENTS",
    "RAW_CPE": "27_ADI_CPE_SHOT_COEFFICIENTS",
}
if not STAGE_DIR.is_dir():
    raise FileNotFoundError(f"입력 폴더 없음: {STAGE_DIR}")
if K_REFERENCE not in ["ADI", "OCO"] or K_PLOT_VALUE not in ["signed_peak_nm", "max_nm", "peak_abs_nm"]:
    raise ValueError("K_REFERENCE 또는 K_PLOT_VALUE 설정을 확인하세요.")
TABLE_DIR, PLOT_DIR = OUTPUT_DIR / "tables", OUTPUT_DIR / "plots"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 110})
input_manifest, output_manifest = [], {}
print("입력:", STAGE_DIR)
print("출력:", OUTPUT_DIR)
''')

md('''## 01. 파일 읽기·정규화·저장 helper
Parquet을 우선 읽고 없으면 같은 이름의 전체 Excel을 읽습니다. `_sample_...xlsx`는 전체 입력으로 사용하지 않습니다. 각 결과는 전체 Parquet/CSV와 Excel(큰 경우 명시한 sample)로 저장합니다.''')
code('io-helpers', '''
def require(frame, columns, name):
    missing = [col for col in columns if col not in frame]
    if missing:
        raise ValueError(f"{name}: 필수 컬럼 누락 {missing}")

def normalize(frame):
    frame = frame.copy()
    aliases = {"lotid": "LOT_ID", "lot_id": "LOT_ID", "slotid": "Wafer", "slot_id": "Wafer"}
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame and value not in frame})
    if "LOT_ID" in frame:
        frame["LOT_ID"] = frame["LOT_ID"].astype("string").str.strip()
    for col in ["Wafer", "photo_transn_seq", "apc_hist_index_no"]:
        if col in frame:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("Int64")
    for col in COORD_COLS + ["pos_x_valn", "pos_y_valn"]:
        if col in frame:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.reset_index(drop=True)

def load_input(name, required=True):
    stem = INPUT_STEMS[name]
    found = next((STAGE_DIR / (stem + suffix) for suffix in [".parquet", ".xlsx"] if (STAGE_DIR / (stem + suffix)).is_file()), None)
    if found is None:
        samples = list(STAGE_DIR.glob(stem + "_sample_*.xlsx"))
        if required:
            raise FileNotFoundError(f"{stem}: 전체 Parquet/Excel이 필요합니다. sample 파일 {len(samples)}개는 분석 입력에서 제외합니다.")
        return None
    frame = pd.read_parquet(found) if found.suffix == ".parquet" else pd.read_excel(found)
    input_manifest.append({"name": name, "file": found.name, "path": str(found), "rows": len(frame), "columns": len(frame.columns), "bytes": found.stat().st_size, "mtime_ns": found.stat().st_mtime_ns})
    return normalize(frame)

def save_table(name, frame, preview=None):
    frame.to_parquet(TABLE_DIR / f"{name}.parquet", index=False)
    frame.to_csv(TABLE_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    if SAVE_EXCEL:
        suffix = f"_sample_{EXCEL_MAX_ROWS}" if len(frame) > EXCEL_MAX_ROWS else ""
        frame.head(EXCEL_MAX_ROWS).to_excel(TABLE_DIR / f"{name}{suffix}.xlsx", index=False, engine="openpyxl")
    output_manifest[name] = {"table": name, "rows": len(frame), "columns": len(frame.columns), "parquet": str(TABLE_DIR / f"{name}.parquet")}
    pd.DataFrame(output_manifest.values()).to_csv(OUTPUT_DIR / "saved_files.csv", index=False, encoding="utf-8-sig")
    cols = [col for col in (preview or list(frame.columns)) if col in frame]
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")
    display(frame[cols].head(PREVIEW_ROWS))
    display(FileLink(os.path.relpath(TABLE_DIR / f"{name}.parquet", Path.cwd()), result_html_prefix="전체 Parquet: "))

def coordinate_key(series):
    values = pd.to_numeric(series, errors="coerce").round(2)
    return values.map(lambda value: f"{value:.2f}" if pd.notna(value) else "<NA>")

def psm_key(frame, from_points=False):
    if from_points:
        chuck = pd.Series(np.where(frame["Wafer"] % 2 == 1, "EX1", "EX2"), index=frame.index)
        return frame["LOT_ID"].astype("string") + "_" + chuck + "_" + coordinate_key(frame["fcp_x"]) + "_" + coordinate_key(frame["fcp_y"])
    return frame["LOT_ID"].astype("string") + "_" + frame["sub_eqp_id"].astype("string").str.strip() + "_" + coordinate_key(frame["pos_x_valn"]) + "_" + coordinate_key(frame["pos_y_valn"])

def add_photo_keys(frame, points, name):
    if "photo_transn_seq" not in PAIR_KEYS or "photo_transn_seq" in frame:
        return frame
    wafer_map = points[PAIR_KEYS].drop_duplicates()
    if wafer_map.duplicated(["LOT_ID", "Wafer"]).any():
        raise ValueError(f"{name}: 같은 LOT/wafer에 여러 photo 이력이 있습니다. 저장된 21/27 계수의 이력을 구분할 수 없습니다.")
    return frame.merge(wafer_map, on=["LOT_ID", "Wafer"], how="inner", validate="m:1")

def row_dict_lookup(frame, keys, name):
    if frame.duplicated(keys).any():
        raise ValueError(f"{name}: 연결 key 중복이 있습니다: {keys}")
    return {key if isinstance(key, tuple) else (key,): group.iloc[0] for key, group in frame.groupby(keys, dropna=False, sort=False)}
''')

md('''## 02. 동일 wafer 선정 및 입력 확인
기본 연결 키는 LOT_ID + Wafer + photo_transn_seq입니다. ADI/OCO 측정점의 좌표나 TEST는 연결 조건으로 사용하지 않습니다. unmatched wafer도 별도 표에 남깁니다.''')
code('load-points', '''
df_adi = load_input("ADI")
df_oco = load_input("OCO")
df_oco_residual = load_input("OCO_RESIDUAL")
for name, frame, values in [("ADI", df_adi, ["X_reg", "Y_reg"]), ("OCO", df_oco, ["X_reg", "Y_reg"]), ("OCO_RESIDUAL", df_oco_residual, ["real_residual_x", "real_residual_y"])]:
    require(frame, PAIR_KEYS + COORD_COLS + values, name)
    if frame[PAIR_KEYS].isna().any().any() or frame["LOT_ID"].eq("").any():
        raise ValueError(f"{name}: wafer 식별자가 비어 있습니다.")
require(df_adi, [f"raw_{axis}" for axis in ANALYSIS_AXES], "ADI 실제 오차: raw")
wafer_match = df_adi[PAIR_KEYS].drop_duplicates().merge(df_oco[PAIR_KEYS].drop_duplicates(), on=PAIR_KEYS, how="outer", indicator="match_status", validate="1:1")
common_wafers = wafer_match.loc[wafer_match["match_status"].eq("both"), PAIR_KEYS]
save_table("02_WAFER_MATCH", wafer_match)
if common_wafers.empty:
    raise ValueError("동일 노광 이력의 공통 ADI/OCO wafer가 없습니다.")
df_adi = df_adi.merge(common_wafers, on=PAIR_KEYS, how="inner", validate="m:1")
df_oco = df_oco.merge(common_wafers, on=PAIR_KEYS, how="inner", validate="m:1")
df_oco_residual = df_oco_residual.merge(common_wafers, on=PAIR_KEYS, how="inner", validate="m:1")
print("공통 wafer:", len(common_wafers), "| ADI points:", len(df_adi), "| OCO points:", len(df_oco))
print("ADI GROUP:", df_adi["GROUP"].astype(str).value_counts().to_dict() if "GROUP" in df_adi else "컬럼 없음")
print("OCO GROUP:", df_oco["GROUP"].astype(str).value_counts().to_dict() if "GROUP" in df_oco else "컬럼 없음")
''')

md('''## 03. Wafer mean·3σ 및 상관 함수
X/Y 각각 유한값으로 mean과 3×표본 표준편차를 계산합니다. 산점도의 점 하나는 wafer 하나이며 Pearson/Spearman과 유효 wafer 수를 기록합니다. 데이터가 거의 일정하거나 유효 wafer가 3개 미만이면 사유와 NaN을 남깁니다.''')
code('statistics', '''
def wafer_statistics(frame, value_cols, prefix):
    work = frame[PAIR_KEYS].copy()
    aggregations = {}
    for axis, col in zip(["x", "y"], value_cols):
        values = pd.to_numeric(frame[col], errors="coerce")
        work[axis] = values.where(np.isfinite(values))
        aggregations[f"{axis}_n_valid"] = (axis, "count")
        aggregations[f"{axis}_mean_nm"] = (axis, "mean")
        aggregations[f"{axis}_std_nm"] = (axis, lambda values: values.std(ddof=STD_DDOF))
    result = work.groupby(PAIR_KEYS, dropna=False).agg(**aggregations).reset_index()
    for axis in ["x", "y"]:
        result[f"{axis}_mean_nm"] *= UM_TO_NM
        result[f"{axis}_std_nm"] *= UM_TO_NM
        result[f"{axis}_3sigma_nm"] = 3 * result[f"{axis}_std_nm"]
    return result.rename(columns={col: prefix + "_" + col for col in result if col not in PAIR_KEYS})

def correlation_result(frame, x_col, y_col):
    values = frame[[x_col, y_col]].apply(pd.to_numeric, errors="coerce")
    valid = np.isfinite(values.to_numpy(float)).all(axis=1)
    x, y = values.loc[valid, x_col].to_numpy(float), values.loc[valid, y_col].to_numpy(float)
    result = dict(n_wafer=len(x), n_excluded=len(frame) - len(x), pearson_r=np.nan, spearman_r=np.nan, slope=np.nan, intercept_nm=np.nan, status="ok")
    if len(x) < MIN_CORR_WAFERS:
        result["status"] = "too_few_wafers"
    elif np.ptp(x) <= CORR_MIN_RANGE_NM or np.ptp(y) <= CORR_MIN_RANGE_NM:
        result["status"] = "constant_or_nearly_constant"
    else:
        result["pearson_r"] = float(pearsonr(x, y).statistic)
        result["spearman_r"] = float(spearmanr(x, y).statistic)
        slope, intercept = np.polyfit(x, y, 1)
        result["slope"], result["intercept_nm"] = float(slope), float(intercept)
    return result

def stats_correlations(frame, scenario, left, right):
    rows = []
    for axis in ["x", "y"]:
        for metric in ["mean", "3sigma"]:
            row = dict(scenario=scenario, axis=axis, metric=metric, x_column=f"{left}_{axis}_{metric}_nm", y_column=f"{right}_{axis}_{metric}_nm")
            row.update(correlation_result(frame, row["x_column"], row["y_column"]))
            rows.append(row)
    return pd.DataFrame(rows)

def scatter_panel(ax, frame, x_col, y_col, title):
    result = correlation_result(frame, x_col, y_col)
    values = frame[[x_col, y_col]].apply(pd.to_numeric, errors="coerce")
    valid = np.isfinite(values.to_numpy(float)).all(axis=1)
    points = frame.loc[valid].copy()
    for lot, group in points.groupby("LOT_ID", sort=True):
        ax.scatter(group[x_col], group[y_col], s=27, alpha=0.8, label=str(lot))
    if not points.empty:
        low, high = float(values.loc[valid].min().min()), float(values.loc[valid].max().max())
        padding = max((high - low) * 0.06, 1e-5)
        limits = [low - padding, high + padding]
        ax.plot(limits, limits, color="0.65", linestyle=":", linewidth=1, label="y=x")
        if result["status"] == "ok":
            grid = np.linspace(points[x_col].min(), points[x_col].max(), 100)
            ax.plot(grid, result["slope"] * grid + result["intercept_nm"], color="black", linewidth=1)
    ax.set(title=title, xlabel=x_col + " [nm]", ylabel=y_col + " [nm]")
    annotation = f"N={result['n_wafer']}  Pearson={result['pearson_r']:.3f}  Spearman={result['spearman_r']:.3f}"
    ax.text(0.03, 0.97, annotation + ("\\n" + result["status"] if result["status"] != "ok" else ""), transform=ax.transAxes, va="top", fontsize=8)
    ax.grid(alpha=0.2)
    if 0 < points["LOT_ID"].nunique() <= 8:
        ax.legend(fontsize=6, loc="best")

def save_figure(fig, name):
    fig.tight_layout()
    fig.savefig(PLOT_DIR / f"{name}.png", dpi=PLOT_DPI, bbox_inches="tight")
    fig.savefig(PLOT_DIR / f"{name}.pdf", bbox_inches="tight")
    if SHOW_PLOTS:
        display(NotebookImage(filename=str(PLOT_DIR / f"{name}.png")))
    plt.close(fig)

def plot_statistics(frame, left, right, name):
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    for ax, (axis, metric) in zip(axes.ravel(), [("x", "mean"), ("x", "3sigma"), ("y", "mean"), ("y", "3sigma")]):
        scatter_panel(ax, frame, f"{left}_{axis}_{metric}_nm", f"{right}_{axis}_{metric}_nm", f"{name}: {axis.upper()} {metric}")
    save_figure(fig, name)
''')

md('''## 04. 참고 ① 계측 출력 ADI Reg ↔ OCO Reg
기존 Reg의 X/Y mean과 3σ를 wafer별로 연결합니다. 실제 ADI 오차인 raw와의 비교는 17번에서 별도로 수행합니다. GROUP·측정 위치가 서로 달라도 저장된 전체 행으로 계산하며, 유효점 수를 함께 저장합니다.''')
code('reg-comparison', '''
adi_reg_stats = wafer_statistics(df_adi, ["X_reg", "Y_reg"], "adi_reg")
oco_reg_stats = wafer_statistics(df_oco, ["X_reg", "Y_reg"], "oco_reg")
reg_pairs = adi_reg_stats.merge(oco_reg_stats, on=PAIR_KEYS, how="inner", validate="1:1")
reg_correlations = stats_correlations(reg_pairs, "REG_vs_REG", "adi_reg", "oco_reg")
save_table("04_REG_WAFER_STATISTICS", reg_pairs)
save_table("04_REG_CORRELATIONS", reg_correlations)
plot_statistics(reg_pairs, "adi_reg", "oco_reg", "04_REG_vs_REG")
''')

md('''## 05. 회사 WK/RK matrix 및 CPE38 matrix
기존 노트북의 식·항 순서·좌표 스케일을 사용합니다. **MRC 적용값은 −matrix×K**, PSM 적용값은 +matrix×K입니다. 따라서 raw에서 추정한 WK/RK beta는 ideal MRC K가 되고, raw 잔차의 CPE beta는 부호를 반대로 바꾼 값이 ideal PSM K입니다.''')
code('models', source_objects(['osr_wk20p_rk20p', 'COEFF_KEYS_DX', 'COEFF_KEYS_DY', 'cpe_38para', 'CPE38_KEYS_DX', 'CPE38_KEYS_DY']) + '''

GLOBAL_NAMES = {"x": COEFF_KEYS_DX, "y": COEFF_KEYS_DY}
CPE_NAMES = {"x": CPE38_KEYS_DX, "y": CPE38_KEYS_DY}
GLOBAL_FIELDS = [f"{name}_{axis.upper()}" for axis in ["x", "y"] for name in GLOBAL_NAMES[axis]]
CPE_FIELDS = [f"{name}_{axis.upper()}" for axis in ["x", "y"] for name in CPE_NAMES[axis]]
APPLIED_CPE_FIELDS = {axis: [f"mrc_k{int(name[2:])}_valn" for name in names] for axis, names in CPE_NAMES.items()}
''')

md('''## 06. 기적용/ideal 계수 읽기
ideal MRC/PSM은 기존 raw 회귀 계수 파일을 읽습니다. **비교 ③의 Reg 회귀 계수와 구분**합니다. 기적용 PSM은 기존 PSM 연결 규칙(LOT/chuck/shot 중심 소수점 2자리)을 사용합니다. PSM lookup 중복이 있으면 최신 event/tkin을 선택하고 별도 표에 남깁니다.''')
code('load-coefficients', '''
applied_mrc = load_input("APPLIED_MRC")
applied_psm = load_input("APPLIED_PSM")
raw_wk, raw_rk = load_input("RAW_WK"), load_input("RAW_RK")
raw_cpe = load_input("RAW_CPE")
for name, frame in [("RAW_WK", raw_wk), ("RAW_RK", raw_rk), ("RAW_CPE", raw_cpe)]:
    require(frame, ["LOT_ID", "Wafer"], name)
raw_wk = add_photo_keys(raw_wk, df_adi, "RAW_WK")
raw_rk = add_photo_keys(raw_rk, df_adi, "RAW_RK")
raw_cpe = add_photo_keys(raw_cpe, df_adi, "RAW_CPE")
wk_fields = [col for col in GLOBAL_FIELDS if col.startswith("WK")]
rk_fields = [col for col in GLOBAL_FIELDS if col.startswith("RK")]
require(raw_wk, PAIR_KEYS + wk_fields, "RAW_WK")
require(raw_rk, PAIR_KEYS + rk_fields, "RAW_RK")
require(raw_cpe, PAIR_KEYS + ["fcp_x", "fcp_y"] + CPE_FIELDS, "RAW_CPE")
ideal_mrc = raw_wk[PAIR_KEYS + wk_fields].merge(raw_rk[PAIR_KEYS + rk_fields], on=PAIR_KEYS, how="outer", validate="1:1")
require(applied_mrc, PAIR_KEYS + [name.lower() for axis in ["x", "y"] for name in GLOBAL_NAMES[axis]], "APPLIED_MRC")
require(applied_psm, ["LOT_ID", "sub_eqp_id", "pos_x_valn", "pos_y_valn"] + sum(APPLIED_CPE_FIELDS.values(), []), "APPLIED_PSM")
applied_psm["_psm_key"] = psm_key(applied_psm)
sort_cols = [col for col in ["event_tsdt", "tkin_tsdt"] if col in applied_psm]
for col in sort_cols:
    applied_psm[col] = pd.to_datetime(applied_psm[col], errors="coerce")
psm_duplicates = applied_psm.loc[applied_psm.duplicated("_psm_key", keep=False)].copy()
if sort_cols:
    applied_psm = applied_psm.sort_values(sort_cols)
applied_psm = applied_psm.drop_duplicates("_psm_key", keep="last")
raw_cpe["_cx"], raw_cpe["_cy"] = coordinate_key(raw_cpe["fcp_x"]), coordinate_key(raw_cpe["fcp_y"])
mrc_old_lookup = row_dict_lookup(applied_mrc, PAIR_KEYS, "APPLIED_MRC")
mrc_ideal_lookup = row_dict_lookup(ideal_mrc, PAIR_KEYS, "IDEAL_MRC")
cpe_ideal_lookup = row_dict_lookup(raw_cpe, PAIR_KEYS + ["_cx", "_cy"], "IDEAL_PSM")
psm_old_lookup = applied_psm.set_index("_psm_key")
save_table("06_PSM_DUPLICATE_KEYS", psm_duplicates)
save_table("06_IDEAL_MRC_RAW_COEFFICIENTS", ideal_mrc)
save_table("06_IDEAL_PSM_RAW_CPE_COEFFICIENTS", raw_cpe.drop(columns=["_cx", "_cy"]))
''')

md('''## 07. ΔK → ADI point 보정 차이 → simulated Reg
이 단계는 기적용/ideal K를 교체하는 기존 시뮬레이션입니다. 14번 이후의 **ADI raw WK/RK 보정량을 OCO Reg에 전달하는 시뮬레이션**과 구분합니다. 시작값을 raw로 일괄 변경하지 마세요. 기존 식에 MRC/PSM 교체 항이 이미 포함되어 있습니다.

ΔK=기적용 K−ideal 적용 K입니다. MRC 차이는 `−B_MRC×ΔK`, PSM 차이는 `+B_CPE38×ΔK`로 계산하고 **sim_Reg = 기존 Reg − ΔMRC − ΔPSM**을 적용합니다. 실제 PERSHOT 값으로 기존 Reg를 재구성하거나 저장 residual로 대체하지 않습니다.

PSM partial NaN은 기존 평가 규칙처럼 0으로 처리하고 원값/처리 여부를 저장합니다. 전체 계수 결측·연결 실패는 NaN과 상태로 남깁니다. 동일 wafer에 여러 노광 이력이 있어 기존 계수의 소속을 구분할 수 없으면 자동 추정하지 않고 오류로 표시합니다.''')
code('simulation-functions', '''
def values_of(row, columns):
    if row is None:
        return np.full(len(columns), np.nan)
    return pd.to_numeric(row.reindex(columns), errors="coerce").to_numpy(dtype=float, na_value=np.nan)

def finite_max(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.max(values)) if len(values) else np.nan

def simulate_adi(points):
    result = points.copy().reset_index(drop=True)
    require(result, ["X_reg", "Y_reg", "PSM_X", "PSM_Y", "mrc_fit_x", "mrc_fit_y"], "ADI simulation")
    for col in ["X_reg", "Y_reg", "PSM_X", "PSM_Y", "mrc_fit_x", "mrc_fit_y"]:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result["_psm_key"] = psm_key(result, from_points=True)
    fit_names = ["mrc_applied", "mrc_ideal", "delta_mrc", "psm_applied", "psm_ideal", "delta_psm", "sim_reg"]
    for axis in ["x", "y"]:
        for name in fit_names:
            result[f"{name}_{axis}_um"] = np.nan
    result["simulation_mrc_status"], result["simulation_psm_status"] = "missing_coefficients", "missing_coefficients"
    mrc_rows, psm_rows, audit_rows = [], [], []
    for key, group in result.groupby(PAIR_KEYS, sort=False, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        identity = dict(zip(PAIR_KEYS, key))
        old_row, ideal_row = mrc_old_lookup.get(key), mrc_ideal_lookup.get(key)
        coords = group[COORD_COLS].to_numpy(float)
        valid_coords = np.isfinite(coords).all(axis=1)
        valid_index = group.index[valid_coords]
        matrices = osr_wk20p_rk20p(*(coords[valid_coords, i] for i in range(4)))
        old_m, new_m = {}, {}
        for axis in ["x", "y"]:
            names = GLOBAL_NAMES[axis]
            old_m[axis] = values_of(old_row, [name.lower() for name in names])
            new_m[axis] = values_of(ideal_row, [f"{name}_{axis.upper()}" for name in names])
            for term, old, ideal in zip(names, old_m[axis], new_m[axis]):
                mrc_rows.append(dict(identity, model="MRC", axis=axis, term=term, k_applied=old, k_ideal=ideal, delta_k=old - ideal, applied_fit_sign=-1))
        mrc_valid = all(np.isfinite(values).all() for values in list(old_m.values()) + list(new_m.values()))
        if mrc_valid:
            result.loc[group.index, "simulation_mrc_status"] = "matched"
            for axis, matrix in zip(["x", "y"], matrices):
                result.loc[valid_index, f"mrc_applied_{axis}_um"] = -matrix @ old_m[axis]
                result.loc[valid_index, f"mrc_ideal_{axis}_um"] = -matrix @ new_m[axis]
                result.loc[valid_index, f"delta_mrc_{axis}_um"] = -matrix @ (old_m[axis] - new_m[axis])
        for (cx, cy), shot in group.groupby(["fcp_x", "fcp_y"], sort=False, dropna=False):
            cx_key, cy_key = coordinate_key(pd.Series([cx])).iloc[0], coordinate_key(pd.Series([cy])).iloc[0]
            ideal_p_row = cpe_ideal_lookup.get(key + (cx_key, cy_key))
            psm_match_key = shot["_psm_key"].iloc[0]
            old_p_row = psm_old_lookup.loc[psm_match_key] if psm_match_key in psm_old_lookup.index else None
            old_stored = {axis: values_of(old_p_row, APPLIED_CPE_FIELDS[axis]) for axis in ["x", "y"]}
            old_all = np.concatenate(list(old_stored.values()))
            old_valid = not np.isnan(old_all).all() and not np.isinf(old_all).any()
            old_p = {axis: np.nan_to_num(values, nan=0.0) for axis, values in old_stored.items()}
            ideal_p = {axis: -values_of(ideal_p_row, [f"{name}_{axis.upper()}" for name in CPE_NAMES[axis]]) for axis in ["x", "y"]}
            ideal_valid = all(np.isfinite(values).all() for values in ideal_p.values())
            partial_nan = bool(np.isnan(old_all).any())
            excluded = [col for col in (old_p_row.index if old_p_row is not None else []) if col.startswith("mrc_k") and col.endswith("_valn") and col not in sum(APPLIED_CPE_FIELDS.values(), [])]
            excluded_values = values_of(old_p_row, excluded)
            outside_count = int(np.sum(np.isfinite(excluded_values) & (excluded_values != 0)))
            for axis in ["x", "y"]:
                for term, stored, old, ideal in zip(CPE_NAMES[axis], old_stored[axis], old_p[axis], ideal_p[axis]):
                    row = dict(identity, fcp_x=cx, fcp_y=cy, model="PSM38", axis=axis, term=term, k_applied_stored=stored, k_applied=old if old_valid else np.nan)
                    row.update(applied_k_was_nan=bool(np.isnan(stored)), k_ideal=ideal, delta_k=old - ideal if old_valid else np.nan, applied_fit_sign=1, nonzero_outside_cpe38=outside_count)
                    psm_rows.append(row)
            if not old_valid or not ideal_valid:
                status = "missing_or_invalid_applied_k" if not old_valid else "missing_or_invalid_ideal_k"
                result.loc[shot.index, "simulation_psm_status"] = status
                continue
            shot_coords = shot[COORD_COLS].to_numpy(float)
            valid = np.isfinite(shot_coords).all(axis=1)
            shot_index = shot.index[valid]
            mx, my = cpe_38para(shot_coords[valid, 2], shot_coords[valid, 3])
            result.loc[shot.index, "simulation_psm_status"] = "partial_nan_zero_filled" if partial_nan else "matched"
            for axis, matrix in zip(["x", "y"], [mx, my]):
                result.loc[shot_index, f"psm_applied_{axis}_um"] = matrix @ old_p[axis]
                result.loc[shot_index, f"psm_ideal_{axis}_um"] = matrix @ ideal_p[axis]
                result.loc[shot_index, f"delta_psm_{axis}_um"] = matrix @ (old_p[axis] - ideal_p[axis])
        for axis in ["x", "y"]:
            index = group.index
            reg = result.loc[index, "X_reg" if axis == "x" else "Y_reg"]
            simulated = reg - result.loc[index, f"delta_mrc_{axis}_um"] - result.loc[index, f"delta_psm_{axis}_um"]
            result.loc[index, f"sim_reg_{axis}_um"] = simulated
            forward = reg - result.loc[index, f"mrc_applied_{axis}_um"] - result.loc[index, f"psm_applied_{axis}_um"] + result.loc[index, f"mrc_ideal_{axis}_um"] + result.loc[index, f"psm_ideal_{axis}_um"]
            checked = np.isfinite(simulated) & np.isfinite(forward)
            rank = int(np.linalg.matrix_rank(matrices[0 if axis == "x" else 1])) if len(valid_index) else 0
            mrc_error = np.abs(result.loc[index, f"mrc_applied_{axis}_um"] - result.loc[index, f"mrc_fit_{axis}"]) * UM_TO_NM
            psm_gap = np.abs(result.loc[index, "PSM_X" if axis == "x" else "PSM_Y"] - result.loc[index, f"psm_applied_{axis}_um"]) * UM_TO_NM
            row = dict(identity, axis=axis, n_points=len(group), n_simulated=int(np.isfinite(simulated).sum()), n_checked=int(checked.sum()), adi_coordinate_matrix_rank=rank)
            row.update(replacement_identity_max_error_nm=finite_max(np.abs(simulated[checked] - forward[checked]) * UM_TO_NM), mrc_rebuild_max_error_nm=finite_max(mrc_error), psm_pershot_max_gap_nm=finite_max(psm_gap))
            audit_rows.append(row)
    result = result.drop(columns="_psm_key")
    for axis in ["x", "y"]:
        result[f"sim_reg_{axis}_nm"] = result[f"sim_reg_{axis}_um"] * UM_TO_NM
        result[f"simulation_valid_{axis}"] = np.isfinite(result[f"sim_reg_{axis}_um"])
    result["simulation_valid"] = result[["simulation_valid_x", "simulation_valid_y"]].all(axis=1)
    return result, pd.DataFrame(mrc_rows), pd.DataFrame(psm_rows), pd.DataFrame(audit_rows)
''')

md('''## 08. ADI simulation 실행 및 계수 차이 저장
MRC/PSM의 기적용·ideal·ΔK를 각각 저장하고, point별 적용값과 Δ보정값을 남깁니다. `psm_pershot_max_gap_nm`은 실제 PERSHOT과 K 재현값의 차이입니다. 이 차이를 덮어쓰지 않으므로 simulation은 저장된 ADI residual과 다를 수 있습니다.''')
code('simulation-run', '''
df_adi_sim, sim_mrc_k, sim_psm_k, sim_audit = simulate_adi(df_adi)
save_table("08_ADI_SIMULATED_POINTS", df_adi_sim, preview=PAIR_KEYS + ["X_reg", "Y_reg", "delta_mrc_x_um", "delta_psm_x_um", "sim_reg_x_nm", "sim_reg_y_nm", "simulation_valid"])
save_table("08_MRC_APPLIED_IDEAL_DELTA_K", sim_mrc_k)
save_table("08_PSM38_APPLIED_IDEAL_DELTA_K", sim_psm_k)
save_table("08_SIMULATION_WAFER_AUDIT", sim_audit)
adi_saved_residual = load_input("ADI_RESIDUAL", required=False)
if adi_saved_residual is not None and "UNIQUE_ID2" in df_adi_sim and "UNIQUE_ID2" in adi_saved_residual:
    keys = PAIR_KEYS + ["UNIQUE_ID2"]
    if not adi_saved_residual.duplicated(keys).any() and not df_adi_sim.duplicated(keys).any():
        residual_check = df_adi_sim[keys + ["sim_reg_x_um", "sim_reg_y_um"]].merge(adi_saved_residual[keys + ["real_residual_x", "real_residual_y"]], on=keys, how="left", validate="1:1")
        for axis in ["x", "y"]:
            residual_check[f"simulation_minus_saved_residual_{axis}_nm"] = (residual_check[f"sim_reg_{axis}_um"] - residual_check[f"real_residual_{axis}"]) * UM_TO_NM
        save_table("08_SIMULATION_VS_SAVED_ADI_RESIDUAL", residual_check)
''')

md('''## 09. 참고 ② 기존 ΔK simulated ADI ↔ OCO real_residual
X/Y 각각 mean과 3σ를 비교합니다. residual mean이 0 근처로 거의 일정하면 mean 상관은 NaN으로 표시될 수 있습니다. 산점도의 원단위는 모두 nm입니다.''')
code('simulation-comparison', '''
adi_sim_stats = wafer_statistics(df_adi_sim, ["sim_reg_x_um", "sim_reg_y_um"], "adi_sim")
oco_residual_stats = wafer_statistics(df_oco_residual, ["real_residual_x", "real_residual_y"], "oco_residual")
sim_pairs = adi_sim_stats.merge(oco_residual_stats, on=PAIR_KEYS, how="left", validate="1:1")
sim_correlations = stats_correlations(sim_pairs, "SIM_ADI_vs_OCO_RESIDUAL", "adi_sim", "oco_residual")
save_table("09_SIMULATION_WAFER_STATISTICS", sim_pairs)
save_table("09_SIMULATION_CORRELATIONS", sim_correlations)
plot_statistics(sim_pairs, "adi_sim", "oco_residual", "09_SIM_ADI_vs_OCO_RESIDUAL")
''')

md('''## 10. Reg에서 wafer WK/RK 계수 새로 추출
이 계수는 계측 출력의 참고 비교용입니다. 실제 ADI 최적화에는 14번에서 별도로 추출하는 `raw_k_adi`를 사용합니다. `reg_k_adi`를 OCO 보정 입력으로 사용하지 않습니다.

ADI/OCO의 **X_reg/Y_reg**를 입력으로 WK 10개+RK 9개를 방향별로 동시 최소제곱 회귀합니다. raw 회귀 계수를 재사용하지 않습니다. 유효점 19개 미만은 생략하고, rank가 19 미만이면 계수 해석에 영향을 주므로 진단에 남깁니다.''')
code('reg-regression', '''
def fit_reg_terms(frame, mode):
    coefficients, diagnostics = [], []
    points = frame.copy().reset_index(drop=True)
    for axis in ["x", "y"]:
        for name in ["reg_wk_fit", "reg_rk_fit", "reg_total_fit", "reg_fit_residual"]:
            points[f"{name}_{axis}_um"] = np.nan
    for key, group in points.groupby(PAIR_KEYS, sort=False, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        identity = dict(zip(PAIR_KEYS, key))
        numeric = group[COORD_COLS + ["X_reg", "Y_reg"]].apply(pd.to_numeric, errors="coerce")
        valid = np.isfinite(numeric.to_numpy(float)).all(axis=1)
        work = numeric.loc[valid]
        diag = dict(identity, mode=mode, n_total=len(group), n_valid=len(work), rank_x=0, rank_y=0, status="skip_too_few_points")
        if len(work) < WK_RK_MIN_POINTS:
            diagnostics.append(diag)
            continue
        matrices = osr_wk20p_rk20p(*(work[col].to_numpy(float) for col in COORD_COLS))
        for axis, matrix, value_col in zip(["x", "y"], matrices, ["X_reg", "Y_reg"]):
            beta, _, rank, singular = np.linalg.lstsq(matrix, work[value_col].to_numpy(float), rcond=None)
            condition = float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 0 else np.inf
            diag[f"rank_{axis}"] = int(rank)
            wk_fit, rk_fit = matrix[:, :10] @ beta[:10], matrix[:, 10:] @ beta[10:]
            points.loc[work.index, f"reg_wk_fit_{axis}_um"] = wk_fit
            points.loc[work.index, f"reg_rk_fit_{axis}_um"] = rk_fit
            points.loc[work.index, f"reg_total_fit_{axis}_um"] = wk_fit + rk_fit
            points.loc[work.index, f"reg_fit_residual_{axis}_um"] = work[value_col].to_numpy(float) - wk_fit - rk_fit
            for term, value in zip(GLOBAL_NAMES[axis], beta):
                coefficients.append(dict(identity, mode=mode, axis=axis, term=term, family=term[:2], k_reg=float(value), n_valid=len(work), rank=int(rank), condition_number=condition, fit_valid=bool(rank == matrix.shape[1])))
        diag["status"] = "ok" if diag["rank_x"] == 19 and diag["rank_y"] == 19 else "rank_deficient"
        diagnostics.append(diag)
    columns = PAIR_KEYS + ["mode", "axis", "term", "family", "k_reg", "n_valid", "rank", "condition_number", "fit_valid"]
    return points, pd.DataFrame(coefficients, columns=columns), pd.DataFrame(diagnostics)

df_adi_reg_fitted, reg_k_adi, reg_diag_adi = fit_reg_terms(df_adi, "ADI")
df_oco_reg_fitted, reg_k_oco, reg_diag_oco = fit_reg_terms(df_oco, "OCO")
save_table("10_ADI_REG_WK_RK_COEFFICIENTS", reg_k_adi)
save_table("10_OCO_REG_WK_RK_COEFFICIENTS", reg_k_oco)
save_table("10_ADI_REG_WK_RK_POINTS", df_adi_reg_fitted)
save_table("10_OCO_REG_WK_RK_POINTS", df_oco_reg_fitted)
save_table("10_REG_WK_RK_DIAGNOSTICS", pd.concat([reg_diag_adi, reg_diag_oco], ignore_index=True))
''')

md('''## 11. Reg K term을 공통 측정점 기준으로 nm 환산
reference wafer별 측정 좌표의 basis를 계산하고 **ADI/OCO K에 같은 basis 범위**를 적용합니다. WK는 fcp 좌표, RK는 shot-local 좌표를 사용합니다. 측정점이 다른 데서 생기는 환산 길이 차이를 방지합니다.

- `signed_peak_nm = K × max(abs(basis)) × 1000`: 기본 그래프, 계수 부호 유지.
- `max_nm = max(basis × K) × 1000`: 실제 signed 최대값.
- `min_nm`, `peak_abs_nm`, `peak_value_nm`도 함께 저장합니다. 마지막 값은 최대 절대 기여점에서의 실제 signed 기여값입니다.

K1/2 translation은 basis=1이므로 그대로 K×1000입니다. 좌표 구성이 달라지면 환산 크기도 달라지므로 reference 종류와 point 수를 저장합니다.''')
code('k-nm-conversion', '''
def convert_reg_k_nm(adi_coeff, oco_coeff, reference):
    coefficient_table = pd.concat([adi_coeff, oco_coeff], ignore_index=True)
    rows = []
    for key, group in reference.groupby(PAIR_KEYS, sort=False, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        identity = dict(zip(PAIR_KEYS, key))
        coords = group[COORD_COLS].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        coords = coords[np.isfinite(coords).all(axis=1)]
        if not len(coords):
            continue
        matrices = osr_wk20p_rk20p(*(coords[:, i] for i in range(4)))
        selected = coefficient_table
        for col, value in identity.items():
            selected = selected.loc[selected[col].eq(value)]
        for axis, matrix in zip(["x", "y"], matrices):
            names = GLOBAL_NAMES[axis]
            for row in selected.loc[selected["axis"].eq(axis)].to_dict("records"):
                basis = matrix[:, names.index(row["term"])]
                beta = row["k_reg"]
                contribution = basis * beta * UM_TO_NM
                row.update(reference_mode=K_REFERENCE, reference_n_points=len(coords), basis_abs_max=float(np.max(np.abs(basis))))
                row.update(min_nm=float(np.min(contribution)), max_nm=float(np.max(contribution)), peak_abs_nm=float(np.max(np.abs(contribution))))
                row.update(signed_peak_nm=float(beta * np.max(np.abs(basis)) * UM_TO_NM), peak_value_nm=float(contribution[np.argmax(np.abs(contribution))]))
                rows.append(row)
    columns = list(coefficient_table.columns) + ["reference_mode", "reference_n_points", "basis_abs_max", "min_nm", "max_nm", "peak_abs_nm", "signed_peak_nm", "peak_value_nm"]
    return pd.DataFrame(rows, columns=columns)

reg_k_nm = convert_reg_k_nm(reg_k_adi, reg_k_oco, df_adi if K_REFERENCE == "ADI" else df_oco)
join_keys = PAIR_KEYS + ["axis", "term", "family"]
adi_k_nm = reg_k_nm.loc[reg_k_nm["mode"].eq("ADI")].drop(columns="mode")
oco_k_nm = reg_k_nm.loc[reg_k_nm["mode"].eq("OCO")].drop(columns="mode")
k_pairs = adi_k_nm.merge(oco_k_nm, on=join_keys, how="outer", suffixes=("_adi", "_oco"), validate="1:1")
k_pairs["both_fits_valid"] = k_pairs["fit_valid_adi"].eq(True) & k_pairs["fit_valid_oco"].eq(True)
save_table("11_REG_K_NM_LONG", reg_k_nm)
save_table("11_REG_K_NM_PAIRED", k_pairs)
''')

md('''## 12. 비교 ③ Reg WK/RK term별 상관 및 그래프
각 K term의 nm 환산값에 대해 wafer 간 Pearson/Spearman을 계산합니다. 기본값은 rank 부족인 계수를 상관·그래프에서 제외하되 원래 계수 표와 진단에는 보존합니다. WK/RK 산점도는 여러 페이지로 나누어 PNG/PDF로 저장합니다.''')
code('k-correlations-and-plots', '''
def select_k_pairs(axis, term):
    selected = k_pairs.loc[k_pairs["axis"].eq(axis) & k_pairs["term"].eq(term)].copy()
    if EXCLUDE_RANK_DEFICIENT_K:
        selected = selected.loc[selected["both_fits_valid"]]
    return selected

k_corr_rows = []
for axis in ["x", "y"]:
    for term in GLOBAL_NAMES[axis]:
        selected = select_k_pairs(axis, term)
        record = dict(scenario="REG_K_vs_REG_K", axis=axis, term=term, family=term[:2], nm_definition=K_PLOT_VALUE, reference_mode=K_REFERENCE)
        record.update(correlation_result(selected, K_PLOT_VALUE + "_adi", K_PLOT_VALUE + "_oco"))
        record["n_excluded"] = len(common_wafers) - record["n_wafer"]
        k_corr_rows.append(record)
k_correlations = pd.DataFrame(k_corr_rows)
save_table("12_REG_K_CORRELATIONS", k_correlations)

for family in ["WK", "RK"]:
    terms = sorted([(axis, term) for axis in ["x", "y"] for term in GLOBAL_NAMES[axis] if term.startswith(family)], key=lambda item: int(item[1][2:]))
    for start in range(0, len(terms), 12):
        fig, axes = plt.subplots(4, 3, figsize=(16, 18))
        page = terms[start:start + 12]
        for ax, (axis, term) in zip(axes.ravel(), page):
            selected = select_k_pairs(axis, term)
            scatter_panel(ax, selected, K_PLOT_VALUE + "_adi", K_PLOT_VALUE + "_oco", f"Reg {term}_{axis.upper()} ({K_REFERENCE} reference)")
        for ax in axes.ravel()[len(page):]:
            ax.set_visible(False)
        save_figure(fig, f"12_REG_K_{family}_{start // 12 + 1:02d}")

fig, axes = plt.subplots(2, 1, figsize=(15, 9))
for ax, family in zip(axes, ["WK", "RK"]):
    selected = k_correlations.loc[k_correlations["family"].eq(family)].copy()
    selected["order"] = selected["term"].str[2:].astype(int)
    selected = selected.sort_values("order")
    positions = np.arange(len(selected))
    ax.bar(positions - 0.18, selected["pearson_r"], width=0.36, label="Pearson")
    ax.bar(positions + 0.18, selected["spearman_r"], width=0.36, label="Spearman")
    ax.set_xticks(positions, selected["term"] + "_" + selected["axis"].str.upper(), rotation=45, ha="right")
    ax.set(ylim=(-1.05, 1.05), ylabel="Correlation", title=f"{family}: {K_PLOT_VALUE}, common {K_REFERENCE} reference")
    ax.axhline(0, color="0.5", linewidth=0.8)
    ax.grid(axis="y", alpha=0.2)
    ax.legend()
save_figure(fig, "12_REG_K_CORRELATION_OVERVIEW")
''')

md('''## 13. 전체 요약·설정·파일 목록
통계와 상관은 분석에 사용한 wafer 수를 포함합니다. 잔차 mean이 거의 0이면 상관이 계산되지 않을 수 있습니다. 회귀가 완료되었다는 사실과 계수의 수치 rank/G-opt/span 조건은 각각의 진단 표로 확인하세요. input_manifest와 run_settings에는 실제 읽은 파일 및 저장된 CPE 설정을 남깁니다.''')
code('summary-and-settings', '''
all_correlations = pd.concat([reg_correlations, sim_correlations, k_correlations], ignore_index=True)
save_table("13_ALL_CORRELATIONS", all_correlations)
save_table("13_INPUT_MANIFEST", pd.DataFrame(input_manifest))
guide = pd.DataFrame([
    ["X_reg/Y_reg", "원본 ADI/OCO 측정값", "µm", "15_*_FINAL"],
    ["k_applied / k_ideal / delta_k", "장비 적용 부호 기준 기적용 K / ideal K / 기적용−ideal", "원본 matrix 계수 스케일", "08_*_APPLIED_IDEAL_DELTA_K"],
    ["delta_mrc_x/y_um", "기적용과 ideal MRC 적용값 차이", "µm", "-B_MRC @ delta_K_MRC"],
    ["delta_psm_x/y_um", "기적용과 ideal CPE38 PSM 적용값 차이", "µm", "+B_CPE38 @ delta_K_PSM"],
    ["sim_reg_x/y_um", "ideal 보정을 적용했다고 가정한 ADI Reg", "µm", "Reg - delta_MRC - delta_PSM"],
    ["*_mean_nm / *_3sigma_nm", "wafer별 평균 / 표본표준편차×3", "nm", "측정값 µm×1000"],
    ["k_reg", "이번 노트북에서 X_reg/Y_reg를 회귀한 WK/RK beta", "원본 matrix 계수 스케일", "raw 회귀 K와 별도"],
    ["signed_peak_nm", "계수 부호를 유지한 최대 절대 기여량", "nm", "K × max(abs(reference basis)) × 1000"],
    ["max_nm / min_nm", "reference point 기여값의 실제 최대/최소", "nm", "max/min(reference basis × K) × 1000"],
    ["peak_abs_nm", "reference point 기여값의 최대 절대값", "nm", "max(abs(reference basis × K)) × 1000"],
    ["fit_valid / both_fits_valid", "Reg 회귀 matrix rank가 각 방향 19인지 여부", "boolean", "K 상관의 기본 포함 조건"],
    ["psm_pershot_max_gap_nm", "실제 PERSHOT과 기적용 CPE38 K 재현값의 최대 차이", "nm", "simulation과 저장 ADI residual이 달라질 수 있는 원인"],
    ["nonzero_outside_cpe38", "DB의 CPE38 지원 외 계수 중 비영 값 개수", "개수", "이번 simulation에서는 지원 외 항의 delta K=0"],
], columns=["컬럼", "설명", "단위", "생성식·출처"])
save_table("13_COLUMN_GUIDE", guide)
source_settings_file = STAGE_DIR.parent / "extension_settings.json"
source_settings = json.loads(source_settings_file.read_text(encoding="utf-8")) if source_settings_file.is_file() else {"status": "source_settings_file_not_found"}
settings = dict(
    pair_keys=PAIR_KEYS, unit_input="um", unit_output="nm", um_to_nm=UM_TO_NM, std_ddof=STD_DDOF,
    group_filter=None, shot_filter=None, point_matching=False, k_reference=K_REFERENCE, k_plot_value=K_PLOT_VALUE,
    exclude_rank_deficient_k=EXCLUDE_RANK_DEFICIENT_K, min_corr_wafers=MIN_CORR_WAFERS, corr_min_range_nm=CORR_MIN_RANGE_NM,
    min_reg_points=WK_RK_MIN_POINTS, ideal_coefficients_source="saved raw WK/RK and CPE38 fits",
    mrc_applied_sign=-1, psm_applied_sign=1, psm_active_terms_x=CPE38_KEYS_DX, psm_active_terms_y=CPE38_KEYS_DY,
    psm_inactive_delta_k=0, source_extension_settings=source_settings, input_files=input_manifest,
)
(OUTPUT_DIR / "run_settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
plot_files = sorted(path.name for path in PLOT_DIR.glob("*.png"))
display(pd.DataFrame({"PNG 파일": plot_files}))
display(all_correlations)
for path in [OUTPUT_DIR / "saved_files.csv", OUTPUT_DIR / "run_settings.json"]:
    display(FileLink(os.path.relpath(path, Path.cwd()), result_html_prefix="결과 목록/설정: "))
print("완료: Reg 통계 / ADI ideal 보정 simulation / Reg WK·RK term 상관")
''')

extension = (Path(__file__).parent / 'ADI_Raw_OCO_Reg_14_19.py').read_text(encoding='utf-8')
for section in extension.split('# %% ')[1:]:
    title, source = section.split('\n', 1)
    md('## ' + title)
    code('adi-raw-' + title.split('.')[0], source)

md('''## 수정·재실행 안내
- 실제 분석 기준은 ADI raw / OCO Reg입니다. 새 결과는 `output_oco_adi_raw_optimized`에 저장합니다.
- ADI raw 회귀와 OCO 시뮬레이션은 14~19번입니다. ADI Reg 회귀 계수를 다시 사용하지 않도록 입력 컬럼 출처를 검사합니다.
- 14~19번만 교체하려면 `ADI_Raw_OCO_Reg_14_19.py`의 `# %%` 구분별 코드를 기존 13번 뒤에 붙입니다. 이전 14~19번은 삭제합니다.
- 새 분석의 X/Y는 `ANALYSIS_AXES`로 지정하며 방향별로 결측을 따로 처리합니다. 기본값은 X만입니다.
- 입력 파일명/경로, nm 환산 방식, reference를 바꾸려면 00에서 수정합니다.
- 통계/상관 정의 변경은 03을 수정하고 04, 09, 12, 13을 다시 실행합니다.
- ΔK simulation 변경은 07부터, Reg 회귀 변경은 10부터 다시 실행합니다.
- `tables`의 Parquet/CSV는 전체 행입니다. Excel sample 파일은 이름으로 구분합니다. `plots`에 PNG/PDF를 저장합니다.
- K의 실제 최대값 비교를 원하면 `K_PLOT_VALUE="max_nm"`로 바꾸고 12~13을 다시 실행합니다. 이때 00을 다시 실행해 입력 경로/목록을 초기화할 필요 없이 값만 새 셀에서 변경해도 됩니다.
- ideal K는 저장된 raw 회귀 결과입니다. 같은 데이터에서 추정한 보정의 simulation이며 독립 측정점에 대한 예측 성능을 의미하지 않습니다.
- 합성 파일로 계산·실행을 검증했으며 실제 사내 stages 데이터는 여기서 읽지 않았습니다.
''')

for index, cell in enumerate(cells):
    cell['id'] = f'correlation-{index:02d}'
notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python'}}, 'cells': cells}
path = ROOT / 'ADI_OCO_Correlation.ipynb'
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Notebook:', path, path.stat().st_size, 'bytes')
print('Code cells:', len([c for c in cells if c['cell_type'] == 'code']))
print('Total code lines:', sum(len(c['source'].splitlines()) for c in cells if c['cell_type'] == 'code'))
print('Maximum cell lines:', max(len(c['source'].splitlines()) for c in cells if c['cell_type'] == 'code'))
