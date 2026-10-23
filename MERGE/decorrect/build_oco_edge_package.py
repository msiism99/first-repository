"""Add OCO edge input support and export exact replacement cells for existing notebooks."""
import json
from pathlib import Path
import runpy
import zipfile

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / "MRC_PSM_decorrect.ipynb"
document = json.loads(MAIN.read_text(encoding="utf-8"))
parts = {}
for part in (HERE / "OCO_Edge_Inputs.py").read_text(encoding="utf-8").split("# %% ")[1:]:
    title, source = part.split("\n", 1)
    parts[int(title.split(".")[0])] = source.rstrip() + "\n"


def cell_at(number):
    if number == 0:
        return next(c for c in document["cells"] if c["cell_type"] == "code" and "class PipelineConfig:" in c["source"])
    index = next(i for i, c in enumerate(document["cells"]) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number:02d}."))
    return document["cells"][index + 1]


settings = cell_at(0)
if "include_oco_edge: bool" not in settings["source"]:
    settings["source"] = settings["source"].replace('    db_user: str = "SIMAXP2"', '    include_oco_edge: bool = True\n    target_mstepseq_oco_edge: str | None = "VC077252"\n    oco_edge_scale: float = 0.6\n    db_user: str = "SIMAXP2"')
    settings["source"] = settings["source"].replace('    def __post_init__(self):\n', '''    def __post_init__(self):
        if not np.isfinite(self.oco_edge_scale) or self.oco_edge_scale < 0:
            raise ValueError("oco_edge_scale은 유한한 0 이상의 수여야 합니다.")
        if self.include_oco_edge and (not self.target_mstepseq_oco_edge or self.target_mstepseq_oco_edge == self.target_mstepseq_oco):
            raise ValueError("Edge 측정 step은 기존 OCO step과 다른 값으로 지정하세요.")
''')
    settings["source"] = settings["source"].replace('cfg.target_mstepseq_oco = "VC077251"\n', 'cfg.target_mstepseq_oco = "VC077251"\ncfg.include_oco_edge = True  # False이면 기존 OCO만 사용\ncfg.target_mstepseq_oco_edge = "VC077252"\ncfg.oco_edge_scale = 0.6  # Edge RAWDATA의 value_x/value_y에만 조회 직후 적용\n')

marker4 = "# OCO edge input extension: matched to the selected main wafers"
cell_at(4)["source"] = cell_at(4)["source"].split(marker4)[0].rstrip() + "\n\n" + marker4 + "\n" + parts[4]
marker5 = "def prepare_oco_raw_source("
original5 = cell_at(5)["source"].split(marker5)[0].split("sql_rawdata_oco =")[0].rstrip()
cell_at(5)["source"] = original5 + "\n\n" + parts[5]
cell_at(6)["source"] = cell_at(6)["source"].replace("latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco,", "latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco_all,")

source8 = cell_at(8)["source"]
if "OCO_PROVENANCE_COLUMNS =" not in source8:
    source8 = source8.replace("FINAL_COLUMNS = [", 'OCO_PROVENANCE_COLUMNS = ["measurement_source", "source_mstepseq", "source_lot_transn_seq", "measurement_scale", "X_reg_original", "Y_reg_original"]\n\nFINAL_COLUMNS = [')
    source8 = source8.replace('    "M_STEPSEQ", "photo_transn_seq", "apc_hist_index_no", "apc_trocs_hist_index_no",\n]', '    "M_STEPSEQ", "photo_transn_seq", "apc_hist_index_no", "apc_trocs_hist_index_no",\n] + OCO_PROVENANCE_COLUMNS')
    source8 = source8.replace('"value_x": "X_reg", "value_y": "Y_reg"}', '"value_x": "X_reg", "value_y": "Y_reg", "value_x_original": "X_reg_original", "value_y_original": "Y_reg_original"}')
    # Same TEST numbers may carry different local coordinates in the two measurement steps.
    # Distinguish their TROCS mark groups without changing wafer/shot regression keys.
    before = '    x, y = df["fcp_x"].to_numpy(float), df["fcp_y"].to_numpy(float)'
    insert = '''    if "measurement_source" in df:
        edge = df["measurement_source"].eq("oco_edge")
        suffix = "_OCO_EDGE_" + integer(df["source_lot_transn_seq"]).astype("string").fillna("unknown")
        for col in ["UNIQUE_ID", "UNIQUE_ID2", "UNIQUE_ID3", "UNIQUE_ID4"]:
            df.loc[edge, col] = df.loc[edge, col] + suffix.loc[edge]
'''
    source8 = source8.replace(before, insert + before)
source8 = source8.replace('assemble_measurements(df_rawdata_oco, df_lotinfo_oco,', 'assemble_measurements(df_rawdata_oco, df_lotinfo_oco_all,')
marker8 = "# OCO edge coverage after the existing group filter"
cell_at(8)["source"] = source8.split(marker8)[0].rstrip() + "\n\n" + marker8 + "\n" + parts[8]

notes = {
    0: "Edge 설정: `include_oco_edge`, `target_mstepseq_oco_edge`, `oco_edge_scale`. 배율은 조회 직후 edge RAWDATA X/Y에만 적용합니다.",
    4: "기존 선정 이후 동일 LOT/slot/photo 이력의 edge step LOTINFO를 별도 조회합니다. Edge가 없어도 기존 wafer는 유지합니다. `04_OCO_EDGE_HISTORY_STATUS`를 확인하세요.",
    5: "기존/edge를 따로 조회하고 edge RAWDATA의 X/Y만 배율 적용 후 합칩니다. TESTDATA 좌표, PERSHOT, MRC 값은 배율 적용 대상이 아닙니다. `*_original`과 출처·배율을 함께 저장합니다.",
    6: "기존/edge 각각의 lot_transn_seq를 보존한 상태에서 최신 batch를 선택합니다. 한쪽의 늦은 측정 시간이 다른 쪽 point를 제거하지 않습니다.",
    8: "기존 OCO E2 필터를 유지합니다. 각 측정 이력의 TESTDATA를 사용하고 출처·원래 X/Y·배율을 보존합니다. `08_OCO_EDGE_COVERAGE`에서 E2 선택 후 point 수를 확인합니다.",
}
for cell in document["cells"]:
    if cell["cell_type"] == "code":
        compile(cell["source"], cell["id"], "exec")
        assert len(cell["source"].splitlines()) < 1000
        cell["execution_count"], cell["outputs"] = None, []
    else:
        for number, note in notes.items():
            if cell["source"].startswith(f"## {number:02d}."):
                cell["source"] = cell["source"].split("\n<!-- oco-edge -->")[0].rstrip() + "\n\n<!-- oco-edge -->\n" + note + "\n"
MAIN.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

intro = dict(cell_type="markdown", id="oco-edge-patch-intro", metadata={}, source="# OCO edge 추가: 교체할 셀만 모은 파일\n독립 실행용이 아닙니다. 기존 노트북의 00(설정), 04, 05, 06, 08번 코드 셀을 아래 내용으로 교체하세요. 00번 import 셀은 유지하고 개인 조회 조건은 옮기세요. 교체 후 커널 재시작 → 00번부터 순서대로 실행합니다.\n")
patch_cells = [intro]
for number in notes:
    patch_cells.append(dict(cell_type="markdown", id=f"oco-edge-patch-heading-{number}", metadata={}, source=f"## {number:02d}. 교체할 코드\n{notes[number]}\n"))
    original = cell_at(number)
    patch_cells.append(dict(cell_type="code", id=f"oco-edge-patch-{number}", metadata={}, source=original["source"], execution_count=None, outputs=[]))
patch_document = dict(nbformat=4, nbformat_minor=5, metadata=document["metadata"], cells=patch_cells)
patch_path = HERE / "OCO_Edge_Replacement_Cells.ipynb"
patch_path.write_text(json.dumps(patch_document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
script_path = HERE / "OCO_Edge_Replacement_Cells.py"
script_path.write_text("\n\n".join(f"# %% {number:02d}. 기존 동일 번호 코드 셀 교체\n" + cell_at(number)["source"] for number in notes), encoding="utf-8")
# Refresh the existing complete packages so they do not contain older main notebooks.
runpy.run_path(str(HERE / "build_wk_rk_fix.py"), run_name="__main__")
with zipfile.ZipFile(HERE / "MRC_PSM_OCO_Edge_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in [MAIN, patch_path, script_path, HERE / "OCO_EDGE_README.md"]:
        archive.writestr(path.name, path.read_bytes())
print("OCO edge package:", (HERE / "MRC_PSM_OCO_Edge_Package.zip").stat().st_size, "bytes")
