"""Build the ADI/OCO E1 coefficient-difference workflow and its replacement notebook."""
import json
from pathlib import Path
import runpy
import zipfile

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / "MRC_PSM_decorrect.ipynb"
document = json.loads(MAIN.read_text(encoding="utf-8"))


def cell_at(number):
    if number == 0:
        return next(c for c in document["cells"] if c["cell_type"] == "code" and "class PipelineConfig:" in c["source"])
    index = next(i for i, c in enumerate(document["cells"]) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number:02d}."))
    return document["cells"][index + 1]


parts = {}
for part in (HERE / "OCO_Edge_Inputs.py").read_text(encoding="utf-8").split("# %% ")[1:]:
    title, source = part.split("\n", 1)
    parts[int(title.split(".")[0])] = source.rstrip() + "\n"

s = cell_at(0)["source"].replace("oco_edge_scale: float = 0.6", "oco_edge_scale: float = 0.5").replace("cfg.oco_edge_scale = 0.6", "cfg.oco_edge_scale = 0.5")
s = s.replace("if self.include_oco_edge and (not self.target_mstepseq_oco_edge or self.target_mstepseq_oco_edge == self.target_mstepseq_oco):", "if self.include_oco_edge and not self.target_mstepseq_oco_edge:")
s = s.replace("Edge 측정 step은 기존 OCO step과 다른 값으로 지정하세요.", "Edge 측정 step을 지정하세요. 기존 step과 같으면 단일 step으로 처리합니다.")
if "kmrc_e1_radius_um:" not in s:
    s = s.replace("    db_user: str", "    kmrc_e1_radius_um: float = 144000.0\n    db_user: str")
    s = s.replace("    def __post_init__(self):\n", "    def __post_init__(self):\n        if not np.isfinite(self.kmrc_e1_radius_um) or self.kmrc_e1_radius_um <= 0:\n            raise ValueError(\"kmrc_e1_radius_um은 유한한 양수여야 합니다.\")\n")
    s = s.replace("cfg.oco_edge_scale = 0.5", "cfg.kmrc_e1_radius_um = 144000.0  # 단일 step의 OCO E1 회귀에만 적용; ADI는 제한하지 않음\ncfg.oco_edge_scale = 0.5")
cell_at(0)["source"] = s

marker4 = "# OCO edge input extension: matched to the selected main wafers"
cell_at(4)["source"] = cell_at(4)["source"].split(marker4)[0].rstrip() + "\n\n" + marker4 + "\n" + parts[4]
s = cell_at(5)["source"].split("def prepare_oco_raw_source(")[0].rstrip()
if "test_group=None" not in s:
    s = s.replace("def rawdata_sql(cfg, lots):", "def rawdata_sql(cfg, lots, test_group=None):")
    s = s.replace('    return f"""', '''    bounds = {"E1": (1, 80), "E2": (81, 160), "E3": (161, 240)}
    group_filter = "" if test_group is None else f"AND r.test_point_no BETWEEN {bounds[test_group][0]} AND {bounds[test_group][1]}"
    return f"""''', 1)
    s = s.replace("LIMIT {cfg.rawdata_row_limit}", "  {group_filter}\nLIMIT {cfg.rawdata_row_limit}")
cell_at(5)["source"] = s + "\n\n" + parts[5]
cell_at(6)["source"] = cell_at(6)["source"].replace("latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco,", "latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco_all,")
s = cell_at(6)["source"]
if "separate_test_groups=False" not in s:
    s = s.replace("def latest_raw_batch(raw, lots, gap_seconds=60):", "def latest_raw_batch(raw, lots, gap_seconds=60, separate_test_groups=False):")
    s = s.replace('    groups = ["lot_transn_seq", "slot_id", "data_kind"]', '''    groups = ["lot_transn_seq", "slot_id", "data_kind"]
    if separate_test_groups:
        require_columns(df, ["test_point_no"], "OCO TEST group batch")
        df["_measurement_group"] = ((pd.to_numeric(df["test_point_no"], errors="coerce") - 1) // 80).astype("Int64")
        groups.append("_measurement_group")''')
    s = s.replace("df.groupby(groups)", "df.groupby(groups, observed=True, dropna=False)")
    s = s.replace('groupby([df[col] for col in groups])', 'groupby([df[col] for col in groups], observed=True, dropna=False)')
    s = s.replace('drop(columns="_batch")', 'drop(columns=["_batch", "_measurement_group"], errors="ignore")')
s = s.replace("latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco_all, cfg.rawdata_gap_seconds)", "latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco_all, cfg.rawdata_gap_seconds, separate_test_groups=True)")
cell_at(6)["source"] = s

s = cell_at(8)["source"]
old_filter = '''        df = df[df["GROUP"].eq(group)].copy()'''
new_filter = '''        source = df["measurement_source"] if "measurement_source" in df else pd.Series("oco_main", index=df.index)
        keep_reference = df["GROUP"].eq("E1") & source.eq("oco_main")
        df["is_kmrc_reference"], df["is_oco_analysis"] = keep_reference, df["GROUP"].eq(group)
        df = df[keep_reference | df["is_oco_analysis"]].copy()'''
s = s.replace(old_filter, new_filter)
if '"is_kmrc_reference", "is_oco_analysis"' not in s:
    s = s.replace('"X_reg_original", "Y_reg_original"]', '"X_reg_original", "Y_reg_original", "is_kmrc_reference", "is_oco_analysis"]')
marker8 = "# OCO edge coverage after the existing group filter"
cell_at(8)["source"] = s.split(marker8)[0].rstrip() + "\n\n" + marker8 + "\n" + parts[8]

s = cell_at(15)["source"].split("\ndef select_oco_model_inputs(")[0].split("\ndf_final_adi =")[0]
cell_at(15)["source"] = s.rstrip() + "\n\n" + (HERE / "KMRC_Raw_Selection.py").read_text(encoding="utf-8")
s = cell_at(20)["source"].split("\ndef attach_measured_shot_indices(")[0].split("\n# K-MRC difference model")[0]
cell_at(20)["source"] = s.rstrip() + "\n\n# K-MRC difference model\n" + (HERE / "KMRC_Regression.py").read_text(encoding="utf-8") + "\n" + (HERE / "WK_RK_Shot_Indices.py").read_text(encoding="utf-8")
s = cell_at(21)["source"].split("\ndf_adi_reg, coef_adi, summary_adi =")[0]
cell_at(21)["source"] = s.rstrip() + "\n\n" + (HERE / "KMRC_21_Execution.py").read_text(encoding="utf-8")
s = cell_at(28)["source"]
if 'kmrc_definition="OCO_E1_RAW_MINUS_ADI_RAW"' not in s:
    s = s.replace("extension_settings = dict(\n", '''extension_settings = dict(
    kmrc_definition="OCO_E1_RAW_MINUS_ADI_RAW", kmrc_parameters_per_axis=19,
    kmrc_e1_radius_um=cfg.kmrc_e1_radius_um, kmrc_adi_radius_limit_um=None, oco_split_steps=OCO_SPLIT_STEPS,
    oco_main_step=cfg.target_mstepseq_oco, oco_edge_step=cfg.target_mstepseq_oco_edge, oco_edge_scale=cfg.oco_edge_scale,
''')
cell_at(28)["source"] = s
cell_at(28)["source"] = cell_at(28)["source"].replace("oco_split_steps=OCO_SPLIT_STEPS", "oco_split_steps=bool(cfg.include_oco_edge and cfg.target_mstepseq_oco_edge != cfg.target_mstepseq_oco)")
notes = {
    0: "동일 step 값이면 단일 조회·배율 1. 별도 edge step의 RAWDATA X/Y에만 기본 배율 0.5. 단일 step의 K-MRC용 OCO E1에만 144000 µm 반경 제한을 적용하며 ADI는 제한하지 않습니다.",
    4: "기존 ADI/OCO 선정 후, 서로 다른 edge step이 있을 때만 동일 LOT/wafer/photo의 edge 이력을 추가 조회합니다. 동일 step은 중복 조회하지 않습니다.",
    5: "기존 OCO E1/E2를 보존합니다. 별도 edge step은 최종 분석 그룹(077: E2, 그 외: E1)만 조회·결합하며 원래 X/Y와 적용 배율을 보존합니다.",
    6: "OCO는 lot_transn_seq·data_kind·TEST 그룹별로 최신 batch를 선택해 E2의 늦은 측정 때문에 E1이 사라지지 않게 합니다. ADI batch 선택은 기존대로 유지합니다.",
    8: "기존 step E1은 K-MRC용으로 보존하고, 최종 분석 그룹(077: E2, 그 외: E1)도 보존합니다. 두 역할을 is_kmrc_reference/is_oco_analysis로 표시합니다.",
    15: "기존 MMO_MRC_EQP 필터 후 OCO 분석 raw와 E1 K-MRC raw를 별도 저장합니다. E1은 main step만 사용합니다. 단일 step에서만 OCO E1 반경 ≤144mm, ADI는 전체 측정점을 유지합니다.",
    20: "기존 축당 19계수 WK/RK 모델을 사용합니다. K-MRC = 회귀(OCO main E1 raw) − 회귀(ADI raw). OCO 분석 위치에서 이 차이 계수를 평가하는 함수를 추가했습니다.",
    21: "ADI 자체 회귀는 유지합니다. OCO는 E1−ADI의 K-MRC를 분석 raw에서 제거하고 raw_minus_total_fit을 만듭니다. 기준 회귀가 불가능한 wafer는 진단·제외 자료에 기록하고 OCO 후속 CPE에서 제외합니다.",
    28: "최종 분해식과 K-MRC·step·배율·반경 설정을 저장합니다. OCO의 WK/RK 제거값은 E2 자체 회귀값이 아니라 K-MRC fitting값입니다.",
}
for cell in document["cells"]:
    if cell["cell_type"] == "code":
        compile(cell["source"], cell["id"], "exec")
        assert len(cell["source"].splitlines()) < 1000
        cell["execution_count"], cell["outputs"] = None, []
    else:
        for number, text in notes.items():
            if cell["source"].startswith(f"## {number:02d}."):
                title = cell["source"].splitlines()[0]
                cell["source"] = title + "\n" + text + "\n"
        if cell["source"].startswith("# ADI/OCO"):
            cell["source"] = "# ADI/OCO — MRC·PSM decorrect → ADI/OCO E1 K-MRC → shot CPE38\n각 셀을 위에서 아래로 실행합니다. OCO K-MRC는 raw 기준 E1 회귀 계수에서 ADI 회귀 계수를 뺀 값입니다. 최종 OCO 분석 그룹은 077 계열이면 E2, 그 외이면 E1입니다.\n"
        if cell["source"].startswith("## 수정·재실행"):
            cell["source"] = cell["source"].replace("18의 요약/저장 helper와 22~26의 CPE 정의 셀", "18의 요약/저장 helper, 20의 shot index helper와 22~26의 CPE 정의 셀")
            cell["source"] = cell["source"].replace("합성 입력에서 원본 `011~013.py`의 값과 비교하고 실제 Jupyter 커널에서 단계별 저장을 검증합니다.", "합성 입력에서 기존 ADI 모델·CPE solver와 새 K-MRC 계수 차이를 검증하고 실제 Jupyter 커널에서 단계별 저장을 확인합니다.")
            if "K-MRC 기준 자료" not in cell["source"]:
                cell["source"] += "\n- K-MRC 기준 자료: `df_oco_e1_raw` / `15_OCO_E1_KMRC_INPUT`. E1 자체 회귀 계수는 `coef_oco_e1`입니다.\n- OCO의 `coef_oco`, `df_wk_coeff_oco`, `df_rk_coeff_oco`는 E1−ADI의 K-MRC 계수입니다. `df_oco_reg`는 분석 raw에서 K-MRC를 제거한 결과입니다.\n- E1 반경/step 모드를 바꾸면 raw 구성을 00번부터 재실행합니다. E1 raw를 직접 바꿨다면 21번에서 다시 계수를 계산하고 27/28번을 갱신합니다.\n"
MAIN.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
runpy.run_path(str(HERE / "build_wk_rk_fix.py"), run_name="__main__")
# Build exact replacement cells after the shared packaging step.
document = json.loads(MAIN.read_text(encoding="utf-8"))
intro = dict(cell_type="markdown", id="kmrc-patch-intro", metadata={}, source="# K-MRC 흐름 수정: 교체할 셀\n독립 실행용이 아닙니다. 00(설정)/04/05/06/08/15/20/21/28의 기존 코드 셀을 교체하고 커널 재시작 후 00번부터 실행합니다. 00번 import 셀은 유지하고 개인 조회 조건은 옮기세요.\n")
patch_cells = [intro]
for number, text in notes.items():
    patch_cells.append(dict(cell_type="markdown", id=f"kmrc-patch-heading-{number}", metadata={}, source=f"## {number:02d}. 교체할 코드\n{text}\n"))
    patch_cells.append(dict(cell_type="code", id=f"kmrc-patch-{number}", metadata={}, execution_count=None, outputs=[], source=cell_at(number)["source"]))
patch_document = dict(nbformat=4, nbformat_minor=5, metadata=document["metadata"], cells=patch_cells)
patch_path = HERE / "KMRC_Replacement_Cells.ipynb"
patch_path.write_text(json.dumps(patch_document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
with zipfile.ZipFile(HERE / "MRC_PSM_KMRC_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in [MAIN, patch_path, HERE / "KMRC_README.md"]:
        archive.writestr(path.name, path.read_bytes())
print("K-MRC ZIP:", (HERE / "MRC_PSM_KMRC_Package.zip").stat().st_size, "bytes")
