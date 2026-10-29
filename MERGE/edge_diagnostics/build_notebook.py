"""Build a standalone notebook with the native CPE38 solver embedded, no local helper imports."""
import ast
import io
import json
from pathlib import Path
import tokenize
import zipfile

HERE = Path(__file__).resolve().parent
document = json.loads((HERE.parent / "MRC_PSM_decorrect.ipynb").read_text(encoding="utf-8"))


def original_code(number):
    index = next(i for i, c in enumerate(document["cells"]) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number}."))
    return document["cells"][index+1]["source"]


solver = {number: original_code(number) for number in range(22, 26)}
names = set()
for source in solver.values():
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
mapping = {name: "EP_"+name if name[0].isupper() else "ep_"+name for name in names}


def rename(source):
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string in mapping:
            token = token._replace(string=mapping[token.string])
        tokens.append(token)
    return tokenize.untokenize(tokens)


def helper(name):
    source = (HERE / name).read_text(encoding="utf-8")
    return source.split("\n", 1)[1] if source.startswith("# %% ") else source


sources = {0: helper("Inputs.py"), 1: helper("Statistics.py"), 2: rename(solver[22]+"\n"+solver[23]), 3: rename(solver[24]+"\n"+solver[25]),
           4: helper("Reference.py"), 5: helper("Run.py"), 6: helper("Plots.py"), 7: helper("Export.py")}
titles = ["제품별 입력 폴더·분석 설정", "통계·저장된 제품별 설정 복원 함수", "기존 CPE38 모델·virtual grid", "기존 ridge/G-opt/span solver",
          "안쪽-only CPE38 참조 및 edge 예측", "제품별 실행·wafer/shot 비교표", "제품별 그래프", "Excel·전체 Parquet·실행 설정 저장"]
intro = """# OCO 제품별 edge / 안쪽 패턴 비교
기존 27·28번 저장 자료만 읽는 독립 노트북입니다. **00번 EP_BASE_DIR를 실제 BASIC 폴더 경로로 지정한 뒤 00→07 순서**로 실행하세요. 기본값은 `E:\\PHOTO_ANALYSIS\\BASIC`입니다. 커널의 임시 작업 폴더를 기준으로 삼지 않습니다.

제품마다 `27_OCO_FINAL_POINTS.parquet`와 같은 실행의 `extension_settings.json` 두 파일이 필요합니다. 전체 Excel도 지원하며 `_sample` 파일은 사용하지 않습니다. 기존 output 폴더 전체를 지정하면 stages 하위도 읽습니다. ADI 및 배율 sweep 파일은 불필요합니다.

배율 적용 전 CPE 입력(기존 decorrection·K-MRC 유지)을 복원합니다. 전체 wafer의 안쪽/edge 입력 통계와, 안쪽 point만으로 CPE38을 추정한 edge 예측 오차를 구분합니다. 예측 불안정/불가능 shot은 이유와 coverage를 기록합니다. **KGVM·KHVF는 Y17, PBVC(VC)는 X21**만 분석합니다. 제품별 방향은 00번 EP_SOURCES의 axis로 지정합니다. 그래프는 각 제품의 지정 방향을 함께 비교하며 축/범례에 X/Y를 명시합니다. DB 조회·기존 파일 수정은 하지 않습니다.
"""
cells = [dict(cell_type="markdown", id="edge-comparison-intro", metadata={}, source=intro)]
for number, source in sources.items():
    compile(source, f"edge-comparison-{number}", "exec")
    assert len(source.splitlines()) < 1000
    cells.append(dict(cell_type="markdown", id=f"edge-comparison-heading-{number}", metadata={}, source=f"## {number:02d}. {titles[number]}\n"))
    cells.append(dict(cell_type="code", id=f"edge-comparison-{number}", metadata={}, source=source.rstrip()+"\n", execution_count=None, outputs=[]))
notebook = dict(nbformat=4, nbformat_minor=5, metadata=document["metadata"], cells=cells)
path = HERE / "OCO_Edge_Inner_Comparison.ipynb"
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+"\n", encoding="utf-8")
with zipfile.ZipFile(HERE / "OCO_Edge_Inner_Comparison_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for member in [path, HERE / "README.md"]:
        archive.writestr(member.name, member.read_bytes())
print("Notebook:", path.stat().st_size, "bytes; max cell:", max(len(s.splitlines()) for s in sources.values()))
print("ZIP:", (HERE / "OCO_Edge_Inner_Comparison_Package.zip").stat().st_size, "bytes")
