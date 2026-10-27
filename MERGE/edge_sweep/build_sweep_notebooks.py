"""Append a self-contained 29-34 scale study, embedding the unchanged CPE solver with private names."""
import ast
import io
import json
from pathlib import Path
import tokenize
import zipfile

HERE = Path(__file__).resolve().parent
MERGE = HERE.parent
document = json.loads((MERGE / "MRC_PSM_decorrect.ipynb").read_text(encoding="utf-8"))


def code_at(number):
    cells = document["cells"]
    i = next(i for i, c in enumerate(cells) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number:02d}."))
    return cells[i+1]["source"]


solver = {n: code_at(n) for n in range(22, 27)}
names = set()
for source in solver.values():
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
mapping = {name: "ES_" + name if name[0].isupper() else "es_" + name for name in names}


def rename(source):
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string in mapping:
            token = token._replace(string=mapping[token.string])
        tokens.append(token)
    return tokenize.untokenize(tokens)


def source_file(name):
    source = (HERE / name).read_text(encoding="utf-8")
    return source.split("\n", 1)[1] if source.startswith("# %% ") else source


sources = {
    29: source_file("Sweep_Inputs.py"),
    30: "# 기존 22·23번 CPE 모델과 virtual grid. es_/ES_ 이름으로 분리해 기존 상태를 보존합니다.\n" + rename(solver[22] + "\n" + solver[23]),
    31: "# 기존 24~26번 solver와 shot별 회귀. 계산 방식은 그대로입니다.\n" + rename(solver[24] + "\n" + solver[25] + "\n" + solver[26]) + "\n" + source_file("Sweep_Settings.py"),
    32: source_file("Sweep_Run.py"), 33: source_file("Sweep_Plots.py"), 34: source_file("Sweep_Report.py"),
}
titles = {
    29: "입력·배율·메트릭 설정 / 저장된 27·28 결과 읽기",
    30: "CPE38 모델·virtual grid 정의",
    31: "CPE38 solver·shot 회귀 / 28번 설정 복원",
    32: "고정 K-MRC에서 영향 shot 재계산 / wafer·shot M3S",
    33: "Wafer·영향 shot 비교 그래프 / 민감도",
    34: "Excel·전체 Parquet·실행 설정 저장",
}
cells = []
for number, source in sources.items():
    compile(source, f"edge-sweep-{number}", "exec")
    assert len(source.splitlines()) < 1000
    cells.append(dict(cell_type="markdown", id=f"edge-sweep-heading-{number}", metadata={}, source=f"## {number}. {titles[number]}\n"))
    cells.append(dict(cell_type="code", id=f"edge-sweep-{number}", metadata={}, source=source.rstrip()+"\n", execution_count=None, outputs=[]))
intro = dict(cell_type="markdown", id="edge-sweep-intro", metadata={}, source="# OCO 외곽 배율 비교: 29~34번\n28번까지 저장한 OCO 결과를 읽어 K-MRC를 고정하고, 144mm 바깥 point가 있는 shot만 CPE를 재계산합니다. DB 조회·기존 29번 context 코드는 실행하지 않습니다. 이 파일만 새 커널에서 29~34번 순서대로 실행하거나 기존 28번 뒤에 복사하세요.\n")
standalone = dict(nbformat=4, nbformat_minor=5, metadata=document["metadata"], cells=[intro]+cells)
append_path = HERE / "OCO_Edge_Sweep_29_34.ipynb"
append_path.write_text(json.dumps(standalone, ensure_ascii=False, indent=1)+"\n", encoding="utf-8")
stop = next(i for i, c in enumerate(document["cells"]) if c["cell_type"] == "markdown" and c["source"].startswith("## 29."))
full = dict(document)
full["cells"] = document["cells"][:stop] + [intro] + cells
full_path = HERE / "MRC_PSM_decorrect_Edge_Sweep.ipynb"
full_path.write_text(json.dumps(full, ensure_ascii=False, indent=1)+"\n", encoding="utf-8")
with zipfile.ZipFile(HERE / "OCO_Edge_Scale_Sweep_Package.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in [append_path, full_path, HERE / "README.md"]:
        archive.writestr(path.name, path.read_bytes())
print("Append notebook:", append_path.stat().st_size, "bytes; max cell:", max(len(s.splitlines()) for s in sources.values()))
print("ZIP:", (HERE / "OCO_Edge_Scale_Sweep_Package.zip").stat().st_size, "bytes")
