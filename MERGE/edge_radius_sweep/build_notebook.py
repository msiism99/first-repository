"""Embed native CPE38 plus saved-data helpers; runtime needs only this notebook and input files."""
import ast
import io
import json
from pathlib import Path
import tokenize
import zipfile

HERE=Path(__file__).resolve().parent
MERGE=HERE.parent
document=json.loads((MERGE/"MRC_PSM_decorrect.ipynb").read_text(encoding="utf-8"))


def original_code(number):
    i=next(i for i,c in enumerate(document["cells"]) if c["cell_type"]=="markdown" and c["source"].startswith(f"## {number}."))
    return document["cells"][i+1]["source"]


solver={n:original_code(n) for n in range(22,26)}
names=set()
for source in solver.values():
    for node in ast.parse(source).body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node,ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t,ast.Name))
mapping={name:"EP_"+name if name[0].isupper() else "ep_"+name for name in names}


def rename(source):
    tokens=[]
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type==tokenize.NAME and token.string in mapping:
            token=token._replace(string=mapping[token.string])
        tokens.append(token)
    return tokenize.untokenize(tokens)


def helper(name):
    source=(HERE/name).read_text(encoding="utf-8")
    return source.split("\n",1)[1] if source.startswith("# %% ") else source


input_source=(MERGE/"edge_diagnostics"/"Inputs.py").read_text(encoding="utf-8")
input_functions="\n\n".join(ast.get_source_segment(input_source,n) for n in ast.parse(input_source).body if isinstance(n,ast.FunctionDef))
sources={0:helper("Inputs.py").replace("# INPUT_HELPERS",input_functions),1:(MERGE/"edge_diagnostics"/"Statistics.py").read_text(encoding="utf-8"),
    2:rename(solver[22]+"\n"+solver[23]),3:rename(solver[24]+"\n"+solver[25]),4:helper("Engine.py"),5:helper("Sampling.py"),6:helper("Run.py"),7:helper("Summary.py"),8:helper("Plots.py"),9:helper("Export.py")}
titles=["제품별 입력·방향·반경·배율 설정","통계 및 저장 설정 복원 함수","기존 CPE38 모델·virtual grid","기존 ridge/G-opt/span solver","Shot 회귀·캐시·평가·재현 검사",
    "실제 point 비율·동일 mixed shot 입력 차이","제품별 실행: 146/147mm × 10~100%","같은 wafer 집합의 비교표·최적 배율","제품·wafer 비교 그래프","Excel·전체 Parquet·설정 저장"]
intro="""# OCO edge 회귀 반경 × 배율 비교
제품마다 기존 `27_OCO_FINAL_POINTS.parquet`와 같은 실행의 `extension_settings.json`만 필요합니다. 기존 output 폴더 또는 두 파일을 모아 둔 폴더를 00번에 지정하세요. **EP_BASE_DIR 기본 E:\\PHOTO_ANALYSIS\\BASIC 경로를 실제 BASIC 경로로 수정한 뒤 00→09 순서로 실행**합니다. DB 조회·기존 notebook 수정은 없습니다.

**KGVM·KHVF는 Y17 / PBVC(VC)는 X21.** K-MRC 고정 상태에서 edge 배율 10~100%(10% 간격), 회귀 반경 146/147mm의 20조건을 제품별 비교합니다. 배율은 PSM 추정에만 사용합니다. 평가는 원래 측정값에서 새 CPE를 뺀 residual로, 같은 ≤144mm / 전체 ≤147mm point에서 수행합니다. 회귀에서 뺀 146~147mm도 평가에는 남깁니다.

실제 wafer/shot별 edge point 비율과 같은 mixed shot의 안쪽·edge 입력 M3S 차이를 함께 저장합니다. Point가 부족해도 para 수는 줄이지 않고 기존 ridge를 적용하되 진단을 남깁니다. 학습 point 0개 등 예측 누락이 생기면 해당 평가 그룹 M3S는 NA입니다. 제품 곡선은 모든 조건에서 유효한 동일 wafer 집합을 사용합니다.

결과는 `output_edge_radius_sweep`에 저장됩니다. 제품별 기존 최적 배율 VM50/VF20/VC40은 00번 reference_scale에 기록하며, 100% 열화와 입력 차이의 관계를 보는 참고값으로만 사용합니다.
"""
cells=[dict(cell_type="markdown",id="edge-radius-intro",metadata={},source=intro)]
for number,source in sources.items():
    compile(source,f"edge-radius-{number}","exec")
    assert len(source.splitlines())<1000
    cells.append(dict(cell_type="markdown",id=f"edge-radius-heading-{number}",metadata={},source=f"## {number:02d}. {titles[number]}\n"))
    cells.append(dict(cell_type="code",id=f"edge-radius-{number}",metadata={},source=source.rstrip()+"\n",execution_count=None,outputs=[]))
notebook=dict(nbformat=4,nbformat_minor=5,metadata=document["metadata"],cells=cells)
path=HERE/"OCO_Edge_Radius_Sweep.ipynb"
path.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
with zipfile.ZipFile(HERE/"OCO_Edge_Radius_Sweep_Package.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for member in [path,HERE/"README.md"]:
        archive.writestr(member.name,member.read_bytes())
print("Notebook:",path.stat().st_size,"bytes; max cell:",max(len(s.splitlines()) for s in sources.values()))
print("ZIP:",(HERE/"OCO_Edge_Radius_Sweep_Package.zip").stat().st_size,"bytes")
