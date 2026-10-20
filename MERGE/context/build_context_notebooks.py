"""Embed the independently executable context cells at the end of the main notebook."""
import ast
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / 'MRC_PSM_decorrect.ipynb'
notebook = json.loads(MAIN.read_text(encoding='utf-8'))
original = [cell for cell in notebook['cells'] if not any(tag.startswith('wafer-context-') for tag in cell.get('metadata', {}).get('tags', []))]
extension = []
for section in (HERE / 'Wafer_Context_29_32.py').read_text(encoding='utf-8').split('# %% ')[1:]:
    title, source = section.split('\n', 1)
    number = title.split('.')[0]
    compile(source, title, 'exec')
    assert len(source.splitlines()) < 1000
    extension.append(dict(cell_type='markdown', id=f'wafer-context-heading-{number}', metadata={'tags': [f'wafer-context-heading-{number}']}, source='## ' + title + '\n'))
    extension.append(dict(cell_type='code', id=f'wafer-context-{number}', metadata={'tags': [f'wafer-context-{number}']}, execution_count=None, outputs=[], source=source.rstrip() + '\n'))
notebook['cells'] = original + extension
assert notebook['cells'][:len(original)] == original
MAIN.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
intro = dict(cell_type='markdown', id='wafer-context-intro', metadata={}, source='# Wafer context 추출: 29~32번\n기존 노트북 끝에 복사하거나 이 파일만 단독 실행합니다. 저장된 stages만 읽으며 DB 조회나 앞 단계 실행은 필요 없습니다. 경로는 29번에서 지정합니다.\n')
standalone = dict(nbformat=4, nbformat_minor=5, metadata=notebook['metadata'], cells=[intro] + extension)
(HERE / 'Wafer_Context_29_32.ipynb').write_text(json.dumps(standalone, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
with zipfile.ZipFile(HERE / 'Wafer_Context_Package.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
    for name, path in {'MRC_PSM_decorrect.ipynb': MAIN, 'Wafer_Context_29_32.ipynb': HERE / 'Wafer_Context_29_32.ipynb', 'Wafer_Context_29_32.py': HERE / 'Wafer_Context_29_32.py', 'README.md': HERE / 'README.md'}.items():
        bundle.writestr(name, path.read_bytes())
print('Updated:', MAIN)
print('Context code lines:', sum(len(c['source'].splitlines()) for c in extension if c['cell_type'] == 'code'))
print('ZIP bytes:', (HERE / 'Wafer_Context_Package.zip').stat().st_size)
