"""Refresh both standalone notebooks and the small Windows download bundles."""
import ast
import json
from pathlib import Path
import runpy
import zipfile

MERGE = Path(__file__).resolve().parents[1]
DECORRECT = MERGE / 'MRC_PSM_decorrect.ipynb'
notebook = json.loads(DECORRECT.read_text(encoding='utf-8'))


def source(cell):
    return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']


original_code = [ast.dump(ast.parse(source(cell))) for cell in notebook['cells'] if cell['cell_type'] == 'code']
notes = {
    0: '\n\n**데이터 해석:** ADI의 실제 오차 기준은 `raw_x/raw_y`입니다. `X_reg/Y_reg`는 계측기 출력이며 raw와 구분합니다. 후속 상관/전달 시뮬레이션의 OCO 기준은 사용자 확인에 따라 **OCO Reg**를 사용합니다. 이 노트북의 20~27번 회귀는 이미 raw 기반이므로 이번 설명 변경으로 계산식을 바꾸지 않습니다.\n',
    23: '\n기존 부호를 유지합니다: `mrc_fit = -B @ K_applied`, `Reg_demrc = Reg - mrc_fit`. 계측 출력 Reg를 실제 ADI 오차로 바로 해석하지 않습니다.\n',
    31: '\nADI는 `raw = Reg - mrc_fit - 실제 PERSHOT`, OCO는 `raw = Reg - mrc_fit - PSM 계수 평가값`입니다. 두 데이터의 PSM 출처가 다르므로 구분합니다. ADI raw가 실제 오차 기준이라는 정의는 이 생성식의 부호를 변경하라는 뜻이 아닙니다.\n',
    43: '\n**회귀 입력은 `raw_x/raw_y`입니다.** 뒤의 `df_adi_reg/df_oco_reg`는 raw 회귀 결과 테이블을 뜻하며, 계측기 `X_reg/Y_reg` 회귀 결과가 아닙니다.\n',
    47: '\nCPE는 raw에서 wafer WK/RK를 제거한 `raw_minus_total_fit_x/y`를 입력으로 사용합니다.\n',
}
for index, note in notes.items():
    cell = notebook['cells'][index]
    assert cell['cell_type'] == 'markdown', index
    if note.strip() not in source(cell):
        cell['source'] = source(cell).rstrip() + note
updated_code = [ast.dump(ast.parse(source(cell))) for cell in notebook['cells'] if cell['cell_type'] == 'code']
assert original_code == updated_code, 'Decorrect numeric code must remain unchanged'
DECORRECT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
runpy.run_path(str(MERGE / 'correlation/build_notebook.py'), run_name='__main__')

files = {
    'ADI_OCO_Correlation.ipynb': MERGE / 'ADI_OCO_Correlation.ipynb',
    'MRC_PSM_decorrect.ipynb': DECORRECT,
    'ADI_Raw_OCO_Reg_14_19.py': MERGE / 'correlation/ADI_Raw_OCO_Reg_14_19.py',
    'README.md': MERGE / 'correlation/README.md',
}
packages = {
    MERGE / 'correlation/ADI_Raw_OCO_Reg_Corrected_Package.zip': files,
    MERGE / 'correlation/ADI_OCO_Correlation_Package.zip': {name: path for name, path in files.items() if name != 'MRC_PSM_decorrect.ipynb'},
    MERGE / 'MRC_PSM_decorrect_00_28.zip': {'MRC_PSM_decorrect.ipynb': DECORRECT},
}
for path, members in packages.items():
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, member in members.items():
            bundle.writestr(name, member.read_bytes())
    with zipfile.ZipFile(path) as bundle:
        assert bundle.testzip() is None
    print('Package:', path, path.stat().st_size, 'bytes')
