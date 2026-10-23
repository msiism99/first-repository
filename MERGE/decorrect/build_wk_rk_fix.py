"""Patch observed grouping and shot metadata; package a DB-free 20/21 rerun notebook."""
import ast
import json
from pathlib import Path
import runpy
import zipfile

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / "MRC_PSM_decorrect.ipynb"
document = json.loads(MAIN.read_text(encoding="utf-8"))


def code_at(number):
    index = next(i for i, cell in enumerate(document["cells"]) if cell["cell_type"] == "markdown" and cell["source"].startswith(f"## {number:02d}."))
    return document["cells"][index + 1]


# Only grouping semantics change; neither the selected rows nor the fitted matrices change.
for number in [15, 18, 20, 21, 26]:
    cell = code_at(number)
    cell["source"] = cell["source"].replace("dropna=False)", "dropna=False, observed=True)")

helper = (HERE / "WK_RK_Shot_Indices.py").read_text(encoding="utf-8")
cell20 = code_at(20)
cell20["source"] = cell20["source"].split("\ndef attach_measured_shot_indices(")[0].rstrip() + "\n\n" + helper
cell21 = code_at(21)
for mode in ["adi", "oco"]:
    old = f"summarize_values(df_{mode}_reg, SHOT_KEYS, wk_rk_values)"
    new = f"attach_measured_shot_indices({old}, df_{mode}_reg)"
    if new not in cell21["source"]:
        cell21["source"] = cell21["source"].replace(old, new)
for cell in document["cells"]:
    if cell["cell_type"] == "code":
        compile(cell["source"], cell["id"], "exec")
        assert len(cell["source"].splitlines()) < 1000
        cell["outputs"], cell["execution_count"] = [], None
    elif cell["source"].startswith("## 21.") and "observed=True" not in cell["source"]:
        cell["source"] += "\n집계는 `observed=True`로 실제 입력에 존재하는 LOT/wafer/shot만 만듭니다. `DieX/DieY`는 실측 index이며 누락 시 `(fcp - MAP_SHIFT) / STEP_PITCH`로 복원합니다. (0,0)은 MAP_SHIFT 위치의 shot이고, 측정 shot 평균으로 재번호를 부여하지 않습니다. 반경으로 edge shot을 삭제하지 않습니다.\n"
MAIN.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def definitions(source, names):
    return "\n\n".join(ast.unparse(node) for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names) + "\n"


def markdown(text, ident):
    return dict(cell_type="markdown", id=ident, metadata={}, source=text)


def code(text, ident):
    compile(text, ident, "exec")
    assert len(text.splitlines()) < 1000
    return dict(cell_type="code", id=ident, metadata={}, source=text, execution_count=None, outputs=[])


setup = '''from pathlib import Path
import os
import numpy as np
import pandas as pd
from IPython.display import display, FileLink

BASE_DIR = Path.cwd()  # C:\\PHOTO_ANALYSIS\\BASIC에 놓고 실행
STAGE_DIR = BASE_DIR / "output_decorrect_notebook" / "stages"
SAVE_PARQUET, SAVE_EXCEL = True, True
PREVIEW_ROWS, EXCEL_PREVIEW_ROWS = 10, 10000

def read_full_stage(name):
    errors = []
    for suffix in [".parquet", ".xlsx"]:
        path = STAGE_DIR / (name + suffix)
        if path.is_file():
            try:
                result = pd.read_parquet(path) if suffix == ".parquet" else pd.read_excel(path)
                print(f"입력: {path.name} ({len(result):,} rows)")
                return result
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
    raise FileNotFoundError(f"{name}: 전체 Parquet/Excel이 필요합니다. _sample 파일은 사용하지 않습니다. " + " | ".join(errors))

def save_stage(name, frame, columns=None):
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")
    selected = [col for col in columns if col in frame] if columns else list(frame.columns)
    display(frame[selected].head(PREVIEW_ROWS))
    if SAVE_PARQUET:
        path = STAGE_DIR / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        display(FileLink(os.path.relpath(path, Path.cwd())))
    if SAVE_EXCEL:
        exported = frame.head(min(EXCEL_PREVIEW_ROWS, 1048575))
        suffix = f"_sample_{len(exported)}" if len(exported) < len(frame) else ""
        path = STAGE_DIR / f"{name}{suffix}.xlsx"
        exported.to_excel(path, index=False, engine="openpyxl")
        display(FileLink(os.path.relpath(path, Path.cwd())))
'''
loads = '''df_adi_trocs = read_full_stage("19_ADI_TROCS_ATTACHED")
df_oco_trocs = read_full_stage("19_OCO_TROCS_ATTACHED")
'''
keys = code_at(18)["source"].split("\ndef summarize_values")[0]
common = next(cell["source"] for cell in document["cells"] if cell["cell_type"] == "code" and "def numeric(" in cell["source"])
helpers = keys + "\n" + definitions(common, {"numeric"}) + definitions(code_at(18)["source"], {"summarize_values"})
audit = '''def wafer_counts(frame):
    return frame.groupby(WAFER_KEYS, observed=True, dropna=False).size().rename("n_measured_points").reset_index()

for mode, source, wafer, shot in [("ADI", df_adi_trocs, df_wk_rk_wafer_adi, df_wk_rk_shot_adi), ("OCO", df_oco_trocs, df_wk_rk_wafer_oco, df_wk_rk_shot_oco)]:
    measured = wafer_counts(source)
    check = measured.merge(wafer[WAFER_KEYS + ["n_points"]], on=WAFER_KEYS, how="outer", validate="1:1", indicator=True)
    assert check["_merge"].eq("both").all() and check["n_measured_points"].eq(check["n_points"]).all()
    assert shot["n_points"].gt(0).all() and shot["n_points"].sum() == len(source)
    selected_name = f"04_LOTINFO_{mode}_SELECTED"
    if any((STAGE_DIR / (selected_name + ext)).is_file() for ext in [".parquet", ".xlsx"]):
        selected = read_full_stage(selected_name).rename(columns={"lotid": "LOT_ID", "slotid": "Wafer"})
        selected = selected[WAFER_KEYS].drop_duplicates()
        scope = selected.merge(measured, on=WAFER_KEYS, how="outer", validate="1:1", indicator=True)
        scope["scope_status"] = scope.pop("_merge").astype(str).map({"both": "selected_and_measured", "left_only": "selected_without_stage19_points", "right_only": "stage19_not_in_selected"})
        save_stage(f"21_{mode}_WK_RK_WAFER_SCOPE", scope)
        if scope["scope_status"].eq("stage19_not_in_selected").any():
            print(f"{mode}: 04와 19의 실행 대상이 다릅니다. 저장 파일이 같은 실행 자료인지 확인하세요.")
    display(wafer[WAFER_KEYS + ["n_points"]])
    print(f"{mode}: 실측 wafer {len(wafer)}, 실측 shot {len(shot)} — 빈 조합 없음")
'''
repair = dict(nbformat=4, nbformat_minor=5, metadata=document["metadata"], cells=[
    markdown("# WK/RK 20·21번 결과 다시 생성\nDB 조회 없이 저장된 19번 전체 point 자료를 읽습니다. 기존 stages의 21번 결과를 덮어씁니다. 입력 19번 및 다른 단계 파일은 수정하지 않습니다. 04번 자료가 있으면 wafer 선정과 실측 목록도 비교합니다.\n", "wk-repair-intro"),
    markdown("## 00. 경로와 저장 설정", "wk-repair-heading-00"), code(setup, "wk-repair-00"),
    markdown("## 01. 저장된 실측 point 읽기", "wk-repair-heading-01"), code(loads, "wk-repair-01"),
    markdown("## 18. 실제 존재하는 그룹만 집계", "wk-repair-heading-18"), code(helpers, "wk-repair-18"),
    markdown("## 20. WK/RK 회귀와 shot index", "wk-repair-heading-20"), code(code_at(20)["source"], "wk-repair-20"),
    markdown("## 21. 재계산 및 저장", "wk-repair-heading-21"), code(code_at(21)["source"], "wk-repair-21"),
    markdown("## 22. 실측 목록과 LOT 선정 검증", "wk-repair-heading-22"), code(audit, "wk-repair-22"),
])
repair_path = HERE / "WK_RK_20_21_Repair.ipynb"
repair_path.write_text(json.dumps(repair, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
runpy.run_path(str(HERE / "build_clean_package.py"), run_name="__main__")
with zipfile.ZipFile(HERE / "MRC_PSM_WK_RK_Fix_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in [MAIN, repair_path, HERE / "WK_RK_FIX_README.md"]:
        archive.writestr(path.name, path.read_bytes())
print("Built main notebook and standalone 20/21 repair package")
