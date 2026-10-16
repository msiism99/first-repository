"""Embed editable input/diagnostic/report cells and the current CPE solver."""
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
source = json.loads((HERE.parent / "MRC_PSM_decorrect.ipynb").read_text(encoding="utf-8"))
cells = []


def markdown(text, tag):
    cells.append(dict(cell_type="markdown",id=tag+"-heading",metadata={},source=text.strip()+"\n"))


def code(text, tag):
    compile(text,tag,"exec")
    assert len(text.splitlines()) < 1000, tag
    cells.append(dict(cell_type="code",id=tag,metadata={"tags":[tag]},execution_count=None,outputs=[],source=text.strip()+"\n"))


markdown(r"""
# ADI/OCO sampling이 X21 / 회전 Y17에 미치는 영향
`C:\PHOTO_ANALYSIS\BASIC\CPE_Sampling_Diagnostics.ipynb`에 놓고 **00~13을 순서대로 실행**합니다. 별도 Python 모듈이나 DB 없이 저장된 stages를 읽습니다. 결과는 새 `output_cpe_sampling_diagnostics`에 저장합니다.

**비교 방향은 기존 실험과 같은 critical X입니다.** ADI와 OCO 각각 대표 wafer 하나를 선택하고 shot 내 좌표를 추출합니다. 측정 배치가 같은 mode 안에서는 대표 sampling으로 진단하며, ADI/OCO 간 다른 point를 1:1로 매칭하지 않습니다.

1. **02:** 대표 wafer/shot 좌표와 반복 layout 목록 저장. 기본은 가능한 같은 wafer에서 가장 완전한 반복 layout을 선택합니다. 00의 `WAFER_SELECTION`으로 원하는 wafer를 지정할 수 있습니다.
2. **03~07:** 원래 CPE 정의·solver·저장 ridge/G-opt/span 설정과 X21/회전Y17 대응표.
3. **08~09:** 공통 평가 grid, rank/항 식별성, alias와 노이즈 증폭 지도.
4. **10:** **동일한 정답 field**를 ADI와 OCO 측정 좌표에서 각각 관측한 것으로 가정하고, 공통 grid에서 복원 오차 비교. 각 단항식과 혼합 패턴을 시험합니다.
5. **11:** ADI는 Y17, OCO는 X21 우세가 같은 field에서도 재현되는지 확인. 입력에 X 값이 있으면 대표 shot의 실제 잔차와 공통항 대비 추가 설명력도 참고로 저장.
6. **12~13:** 그림과 `CPE_Sampling_Diagnostics.xlsx` 저장.

**좌표만으로 실제 오차 원인을 확정할 수는 없습니다.** 이 분석은 어떤 성분이 관측 가능하고, sampling과 제약 때문에 어떤 패턴에서 우열이 달라질 수 있는지 확인합니다. 합성 패턴의 빈도는 실제 원인의 확률이 아닙니다.

각 정답 패턴은 공통 grid의 RMS가 1 nm가 되도록 정규화합니다. noise 기본값 0.2 nm는 **가정값**이며 00에서 바꿀 수 있습니다. 공통 grid의 전체 영역과 두 sampling의 convex hull 교집합에서의 오차를 별도로 저장합니다. 학습점 잔차가 작아도 전체 field가 잘 복원된다는 뜻은 아니므로 `grid_rmse_nm`을 함께 보세요.
""","sampling-intro")

for section in (HERE / "Sampling_Inputs.py").read_text(encoding="utf-8").split("# %% ")[1:]:
    title,body = section.split("\n",1)
    number = int(title.split(".",1)[0])
    markdown("## "+title,f"sampling-{number:02d}")
    code(body,f"sampling-{number:02d}")
for target,original in enumerate(range(22,26),start=3):
    index = next(i for i,cell in enumerate(source["cells"]) if cell["cell_type"] == "markdown" and cell["source"].startswith(f"## {original}."))
    heading = source["cells"][index]["source"].splitlines()[0].split(". ",1)[1]
    markdown(f"## {target:02d}. {heading}\n원본 solver 정의입니다. 07에서 저장 설정과 override를 적용합니다.",f"sampling-core-{target:02d}")
    code(source["cells"][index+1]["source"],f"sampling-core-{target:02d}")
rotation = (HERE.parent / "rotation/CPE_Critical_Rotation.py").read_text(encoding="utf-8")
settings = next(section for section in rotation.split("# %% ")[1:] if section.startswith("07."))
title,body = settings.split("\n",1)
markdown("## "+title,"sampling-07")
code(body,"sampling-07")
for filename in ["Sampling_Diagnostics.py","Sampling_Experiments.py","Sampling_Report.py"]:
    for section in (HERE / filename).read_text(encoding="utf-8").split("# %% ")[1:]:
        title,body = section.split("\n",1)
        number = int(title.split(".",1)[0])
        markdown("## "+title,f"sampling-{number:02d}")
        code(body,f"sampling-{number:02d}")
destination = HERE / "CPE_Sampling_Diagnostics.ipynb"
notebook = dict(nbformat=4,nbformat_minor=5,metadata=source["metadata"],cells=cells)
destination.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
with zipfile.ZipFile(HERE / "CPE_Sampling_Diagnostics_Package.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name in [destination.name,"README.md"]:
        archive.writestr(name,(HERE / name).read_bytes())
print("Notebook bytes:",destination.stat().st_size)
print("Code cells:",sum(cell["cell_type"] == "code" for cell in cells))
print("Largest cell:",max(len(cell["source"].splitlines()) for cell in cells if cell["cell_type"] == "code"))
print("ZIP bytes:",(HERE / "CPE_Sampling_Diagnostics_Package.zip").stat().st_size)
