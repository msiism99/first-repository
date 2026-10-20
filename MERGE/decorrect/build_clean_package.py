"""Remove snapshot/replay and saved-file manifests, preserving every numeric function."""
import ast
import json
from pathlib import Path
import re
import runpy
import zipfile

HERE = Path(__file__).resolve().parent
MERGE = HERE.parent
MAIN = MERGE / "MRC_PSM_decorrect.ipynb"
notebook = json.loads(MAIN.read_text(encoding="utf-8"))

STORAGE_CODE = '''class QuerySource:
    def __init__(self, get_data=None):
        self.get_data = get_data
        self.cache = {}
        self.query_count = 0

    def fetch(self, name, sql, reuse=True):
        signature = hashlib.sha256(" ".join(sql.split()).encode()).hexdigest()
        if reuse and signature in self.cache:
            frame = self.cache[signature]
            LOG.info("%s: 동일 SQL 조회 결과 재사용", name)
        else:
            if self.get_data is None:
                try:
                    import bigdataquery as bdq
                except ModuleNotFoundError as exc:
                    raise RuntimeError("사내 DB 조회에는 bigdataquery가 필요합니다. 사내 환경에서 실행하세요.") from exc
                self.get_data = bdq.getData
            frame = self.get_data(sql)
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"{name}: getData는 DataFrame을 반환해야 합니다.")
            self.query_count += 1
            if reuse:
                self.cache[signature] = frame
        LOG.info("%s: %s rows", name, len(frame))
        return frame.copy() if reuse else frame

    def release_cache(self):
        self.cache.clear()

source = QuerySource()
cfg.reference_date = cfg.reference_date or pd.Timestamp.today().date().isoformat()

def fetch_frame(name, sql, reuse=True):
    return source.fetch(name, sql, reuse=reuse)

STAGE_DIR = OUTPUT_DIR / "stages"
STAGE_DIR.mkdir(parents=True, exist_ok=True)

def save_stage(name, frame, columns=None):
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")
    selected = [col for col in columns if col in frame] if columns else list(frame.columns)
    display(frame[selected].head(PREVIEW_ROWS))
    paths = []
    if SAVE_PARQUET:
        path = STAGE_DIR / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        paths.append(("parquet_full", path, len(frame)))
    if SAVE_EXCEL:
        limit = min(EXCEL_PREVIEW_ROWS, cfg.max_excel_rows)
        exported = frame.head(limit)
        suffix = f"_sample_{len(exported)}" if len(frame) > limit else ""
        path = STAGE_DIR / f"{name}{suffix}.xlsx"
        exported.to_excel(path, index=False, engine="openpyxl")
        paths.append(("excel_sample" if suffix else "excel_full", path, len(exported)))
    for kind, path, exported_rows in paths:
        display(FileLink(os.path.relpath(path, Path.cwd()), result_html_prefix=f"{kind} ({exported_rows:,}행): "))

print("조회: 사내 DB | ADI 기준일:", cfg.reference_date)
'''


def numeric_functions(document):
    result = {}
    for cell in document["cells"]:
        if cell["cell_type"] != "code":
            continue
        for node in ast.parse(cell["source"]).body:
            if isinstance(node, ast.FunctionDef) and node.name not in {"save_stage", "fetch_frame", "snapshot_path", "ctx_read"}:
                result[node.name] = ast.dump(node)
    return result


before = numeric_functions(notebook)
for cell in notebook["cells"]:
    source = cell["source"]
    if cell["cell_type"] == "code":
        if source.startswith("class QuerySource:"):
            source = STORAGE_CODE
        else:
            source = re.sub(r', existing_parquet=snapshot_path\("[^"]+"\)', "", source)
            source = "\n".join(line for line in source.splitlines() if not any(token in line for token in ["save_snapshots", "DATA_MODE =", "REPLAY_DIR =", "df_saved_files", "saved_files.csv", "source.save_manifest"]))+"\n"
            source = source.replace("None이면 live/replay 조회", "None이면 사내 DB 조회")
            source = source.replace("from dataclasses import dataclass, asdict", "from dataclasses import dataclass")
        compile(source,cell.get("id","cell"),"exec")
        cell["execution_count"],cell["outputs"] = None,[]
    else:
        source = source.replace("분해식 검증, wafer별/shot별 최종 요약, 저장 파일 목록과 실행 설정 저장.", "분해식 검증, wafer별/shot별 최종 요약과 실행 설정 저장.")
        source = source.replace("각 셀에서 파일 링크를 표시하며 `saved_files.csv`에 목록을 기록합니다.", "각 셀에서 저장한 파일의 링크를 표시합니다. 조회 원본과 중간 결과는 모두 `stages`에 저장합니다.")
        source = source.replace("live 모드는 사내 `bigdataquery`가 필요합니다. replay는 저장된 조회 스냅샷을 사용합니다. 과거 00~15 스냅샷에는 TROCS 조회가 없으므로 16에서 새로 조회하거나 해당 SQL 결과 파일을 지정해야 합니다. 생산 DB 실행은 사내 환경에서 확인하세요.", "사내 `bigdataquery`로 DB를 조회합니다. TROCS는 16에서 조회하거나 해당 SQL 결과 파일을 지정합니다.")
        source = source.replace('먼저 아래 설정을 수정합니다. `DATA_MODE="replay"`이면 `REPLAY_DIR`에 기존 snapshots 폴더를 지정하세요.', '먼저 아래 설정을 수정합니다. 조회 원본과 단계별 결과는 `OUTPUT_DIR / "stages"`에 저장합니다.')
        source = source.replace("큰 조회 결과는 snapshots의 전체 Parquet을 연결해서 중복 저장을 줄입니다.", "조회 원본도 `stages`에 전체 Parquet과 Excel 미리보기로 저장합니다.")
        source = source.replace("## 28. 최종 분해식 확인 및 전체 저장 목록", "## 28. 최종 분해식 확인 및 실행 설정 저장")
        source = source.replace("·조회 연결·", "·DB 조회 연결·")
        source = re.sub(r"(?:DB )+조회 연결", "DB 조회 연결", source)
        source = source.replace("df_final_adi/oco, df_wafer_summary와 df_saved_files가", "df_final_adi/oco와 df_wafer_summary가")
        source = source.replace("과거 스냅샷으로 15까지 실행했다면", "TROCS를 별도로 조회했다면")
        source = source.replace("파일 지정 없이 replay하려면 `trocs_shot` 스냅샷이 필요합니다.", "파일을 지정하지 않으면 아래 SQL로 사내 DB를 조회합니다.")
        source = source.replace(" replay는 저장 당시 SQL 조건과 일치해야 합니다.", "")
    cell["source"] = source
assert numeric_functions(notebook) == before, "Numeric/SQL/context functions must not change"
MAIN.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
runpy.run_path(str(MERGE / "context/build_context_notebooks.py"),run_name="__main__")
current = json.loads(MAIN.read_text(encoding="utf-8"))
assert numeric_functions(current) == before, "Only storage functions may change"
text = "\n".join(cell["source"] for cell in current["cells"])
assert not any(token in text for token in ["snapshot", "스냅샷", "DATA_MODE", "REPLAY_DIR", "replay", "saved_files", "stage_files", "save_manifest", "existing_parquet"])
packages = {
    HERE / "MRC_PSM_decorrect_Clean_Package.zip": {"MRC_PSM_decorrect.ipynb": MAIN, "README.md": HERE / "README.md"},
    MERGE / "MRC_PSM_decorrect_00_28.zip": {"MRC_PSM_decorrect.ipynb": MAIN},
}
for path,members in packages.items():
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,member in members.items():
            archive.writestr(name,member.read_bytes())
    print("Package:",path.name,path.stat().st_size,"bytes")
print("Unchanged numeric/SQL functions:",len(before))
