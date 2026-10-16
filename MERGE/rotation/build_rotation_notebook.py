"""Build a self-contained notebook; no runtime dependency on source Python files."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "MRC_PSM_decorrect.ipynb"
reference = json.loads(SOURCE.read_text(encoding="utf-8"))
cells = []


def markdown(text, tag):
    cells.append(dict(cell_type="markdown", id=tag+"-heading", metadata={}, source=text.strip()+"\n"))


def code(text, tag):
    compile(text, tag, "exec")
    assert len(text.splitlines()) < 1000, tag
    cells.append(dict(cell_type="code", id=tag, metadata={"tags": [tag]}, execution_count=None, outputs=[], source=text.strip()+"\n"))


markdown(r"""
# Critical X: X21 / 90° 회전 Y17 비교
이 파일을 `C:\PHOTO_ANALYSIS\BASIC\CPE_Critical_Rotation.ipynb`에 놓고 **00부터 순서대로 실행**합니다. 기존 `stages`의 Parquet/전체 Excel만 읽으며 DB 조회나 원본 노트북 실행은 필요하지 않습니다.

문제 제품의 **같은 X 오차·같은 측정 point**에 두 모델을 적용합니다. 입력은 `21_ADI_WK_RK_REMOVED` / `21_OCO_WK_RK_REMOVED`의 `raw_minus_total_fit_x`입니다. 21 파일이 없으면 같은 입력 컬럼이 있는 27 FINAL_POINTS를 사용합니다. **WK/RK는 다시 계산하지 않습니다.**

- **X21_NATIVE:** 기존 장비 좌표의 X21 모델과 X측 ridge/G-opt/span 설정.
- **ROT_Y17_NATIVE:** 로컬 좌표와 critical X 성분을 ±90° 회전 → Y17과 Y측 설정으로 회귀 → 보정값을 원래 장비 X로 복원.
- **OLS_DIAGNOSTIC:** 두 항 구성의 제약 없는 회귀도 별도 저장합니다. 실제 보정 설정 결과와 구분해서 보세요.

**원래 좌표에서 X21과 회전 Y17은 포함관계가 아닙니다.** 공통 단항식은 12개이고, X21만 있는 항은 9개, 회전 Y17만 있는 항은 5개입니다. 예를 들어 원래 좌표의 `x^4`는 X21에 없고 회전 Y17에는 있습니다. 07에서 전체 대응표를 저장합니다.

00의 `FILTERS`에 문제 제품의 LOT/recipe 등을 지정하세요. 필요하면 앞서 저장한 `output_wafer_context\wafer_context.parquet`도 자동 연결합니다. **필터가 비어 있으면 선택한 mode의 전체 입력을 critical X 제품으로 취급합니다.** Y 측정값은 사용하지 않습니다.

원단위는 µm, 통계 출력은 nm입니다. 결과는 새 `output_cpe_critical_rotation`에 저장합니다. 제거된 CPE가 작다는 것만으로 개선을 판단하지 말고 **최종 residual의 3σ 및 |mean|+3σ**를 함께 보세요. 학습에 사용한 point의 회귀 결과이며 장비에 실제 보정을 적용한 결과는 아닙니다.
""", "rotation-intro")

sections = (HERE / "CPE_Critical_Rotation.py").read_text(encoding="utf-8").split("# %% ")[1:]
for section in sections:
    title, body = section.split("\n", 1)
    number = int(title.split(".", 1)[0])
    if number == 7:
        for target, original in enumerate(range(22, 26), start=3):
            index = next(i for i,cell in enumerate(reference["cells"]) if cell["cell_type"] == "markdown" and cell["source"].startswith(f"## {original}."))
            source = reference["cells"][index+1]["source"]
            heading = reference["cells"][index]["source"].splitlines()[0].split(". ", 1)[1]
            markdown(f"## {target:02d}. {heading}\n원본 MRC_PSM_decorrect의 {original}번 정의를 그대로 포함합니다. 실제 설정은 07에서 저장 설정 및 00의 override를 반영합니다.", f"rotation-{target:02d}")
            code(source, f"rotation-core-{target:02d}")
    markdown("## "+title, f"rotation-{number:02d}")
    code(body, f"rotation-{number:02d}")

notebook = dict(nbformat=4, nbformat_minor=5, metadata={**reference["metadata"], "rotation_source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()}, cells=cells)
destination = HERE / "CPE_Critical_Rotation.ipynb"
destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+"\n", encoding="utf-8")
with zipfile.ZipFile(HERE / "CPE_Critical_Rotation_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name in [destination.name, "README.md"]:
        archive.writestr(name, (HERE / name).read_bytes())
print("Notebook bytes:", destination.stat().st_size)
print("Code cells:", len([cell for cell in cells if cell["cell_type"] == "code"]))
print("Largest code cell:", max(len(cell["source"].splitlines()) for cell in cells if cell["cell_type"] == "code"))
print("ZIP bytes:", (HERE / "CPE_Critical_Rotation_Package.zip").stat().st_size)
