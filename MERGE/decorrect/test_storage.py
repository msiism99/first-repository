"""Validate notebook storage and final exports without accessing a production database."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import nbformat
from nbclient import NotebookClient
import pandas as pd

MAIN = Path(__file__).resolve().parents[1] / "MRC_PSM_decorrect.ipynb"


def code_after_heading(notebook, heading):
    index = next(i for i,cell in enumerate(notebook.cells) if cell.cell_type == "markdown" and cell.source.startswith(heading))
    return notebook.cells[index+1].source


class StorageTests(unittest.TestCase):
    def test_notebook_has_no_removed_storage_dependencies(self):
        notebook = nbformat.read(MAIN,as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            for token in ["snapshot","스냅샷","REPLAY_DIR","DATA_MODE","replay","saved_files","stage_files","save_manifest","existing_parquet"]:
                self.assertNotIn(token,cell.source)
            if cell.cell_type == "code":
                compile(cell.source,cell.id,"exec")
                self.assertLess(len(cell.source.splitlines()),1000)
                self.assertFalse(cell.outputs)
        storage = next(cell.source for cell in notebook.cells if cell.cell_type == "code" and "def save_stage(" in cell.source)
        self.assertIn("frame.to_parquet(path, index=False)",storage.split("def save_stage")[1])

    def test_actual_kernel_queries_and_15_28_exports(self):
        with tempfile.TemporaryDirectory(prefix="decorrect-storage-") as temp:
            base = Path(temp)
            original = nbformat.read(MAIN,as_version=4)
            setup = code_after_heading(original,"## 00.")
            # 00 consists of import and configuration cells.
            index = next(i for i,c in enumerate(original.cells) if c.cell_type == "code" and c.source.startswith("@dataclass\nclass PipelineConfig"))
            settings = original.cells[index].source
            lines = settings.splitlines()
            overrides = dict(OUTPUT_DIR=f"Path({str(base / 'output_decorrect_notebook')!r})",EXCEL_PREVIEW_ROWS="2",PREVIEW_ROWS="2")
            for node in ast.parse(settings).body:
                if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in overrides:
                    name = node.targets[0].id
                    lines[node.lineno-1] = f"{name} = {overrides[name]}"
            settings = "\n".join(lines)
            helper_index = next(i for i,c in enumerate(original.cells) if c.cell_type == "code" and c.source.startswith("class QuerySource:"))
            cells = [nbformat.v4.new_code_cell(setup),nbformat.v4.new_code_cell(settings),nbformat.v4.new_code_cell(original.cells[helper_index-1].source),nbformat.v4.new_code_cell(original.cells[helper_index].source)]
            cells.append(nbformat.v4.new_code_cell('''
import sys
import types
calls = []
query_frame = pd.DataFrame({"value":[1.,2.,3.,4.,5.],"name":["A","B","C","D","E"]})
def get_data(sql):
    calls.append(sql)
    return query_frame.copy(deep=True)
sys.modules["bigdataquery"] = types.SimpleNamespace(getData=get_data)
first = fetch_frame("first", "SELECT  fixture")
first.loc[0,"value"] = -99
second = fetch_frame("second", "  SELECT fixture  ")
assert second.loc[0,"value"] == 1
assert source.query_count == 1 and len(calls) == 1
uncached = fetch_frame("uncached", "SELECT fixture", reuse=False)
assert source.query_count == 2
save_stage("05_RAWDATA_ADI_QUERY",second)
save_stage("07_F1_QUERY",second)
save_stage("EMPTY_QUERY",query_frame.iloc[:0])
source.release_cache()
fetch_frame("third", "SELECT fixture")
assert source.query_count == 3
bad = QuerySource(get_data=lambda sql: [])
try:
    bad.fetch("bad", "SELECT bad")
except TypeError:
    pass
else:
    raise AssertionError("invalid database return type must be rejected")
pd.testing.assert_frame_equal(pd.read_parquet(STAGE_DIR / "05_RAWDATA_ADI_QUERY.parquet"),query_frame)
assert len(pd.read_excel(STAGE_DIR / "05_RAWDATA_ADI_QUERY_sample_2.xlsx")) == 2
df_adi_raw = pd.DataFrame({"LOT_ID":["LOT_A"]*5,"Wafer":[9]*5,"raw_x":[.001,.002,np.nan,.004,.005],"raw_y":[.002,.003,np.nan,.005,.006],"decorrect_valid":[True,True,False,True,True],"mrc_status":["matched"]*5,"psm_fit_status":["matched"]*5,"MMO_MRC_EQP":["EQP","EQP","EQP",None,""]})
df_oco_raw = df_adi_raw.copy(deep=True)
raw_before = df_adi_raw.copy(deep=True)
raw_preview = ["LOT_ID","Wafer","raw_x","raw_y","decorrect_valid"]
'''))
            cells.append(nbformat.v4.new_code_cell(code_after_heading(original,"## 15.")))
            # Prepare already-computed components to exercise the final export cell unchanged.
            definitions = ast.parse(code_after_heading(original,"## 18."))
            summary_function = next(node for node in definitions.body if isinstance(node,ast.FunctionDef) and node.name == "summarize_values")
            cells.append(nbformat.v4.new_code_cell(code_after_heading(original,"## 22.")))
            cells.append(nbformat.v4.new_code_cell(ast.unparse(summary_function)+'''
pd.testing.assert_frame_equal(df_adi_raw,raw_before)
assert len(df_final_adi) == 3
assert not df_final_adi["decorrect_valid"].iloc[2]
WAFER_KEYS = ["LOT_ID","Wafer"]
SHOT_KEYS = WAFER_KEYS+["fcp_x","fcp_y"]
df_adi_cpe,df_oco_cpe = df_final_adi.copy(),df_final_oco.copy()
for frame in [df_adi_cpe,df_oco_cpe]:
    frame["fcp_x"],frame["fcp_y"] = 0.,0.
    for axis in ["x","y"]:
        frame[f"trocs_fit_{axis}"] = .0001
        frame[f"wk_fit_{axis}"] = .0001
        frame[f"rk_fit_{axis}"] = .0002
        frame[f"CPE_fit_{axis}"] = .0003
        frame[f"real_residual_{axis}"] = frame[f"raw_{axis}"]-.0006
TROCS_WAFER_RADIUS,TROCS_QUERY_FILE,WK_RK_MIN_POINTS = 147000.,None,19
cpe_options = dict(span_mode=SPAN_MODE,ridge_regression=RIDGE_REGRESSION,gopt_spec=G_OPT_SPEC,gopt_type=G_OPTIMAL_TYPE)
'''))
            cells.append(nbformat.v4.new_code_cell(code_after_heading(original,"## 28.")))
            cells.append(nbformat.v4.new_code_cell('''
assert df_decomposition_check["passed"].all()
assert df_decomposition_check["n_checked"].eq(2).all()
pd.testing.assert_frame_equal(pd.read_parquet(STAGE_DIR / "15_ADI_FINAL.parquet"),df_final_adi.reset_index(drop=True))
assert len(pd.read_excel(STAGE_DIR / "15_ADI_FINAL_sample_2.xlsx")) == 2
assert (OUTPUT_DIR / "extension_settings.json").is_file()
assert not (OUTPUT_DIR / "snapshots").exists()
assert not (OUTPUT_DIR / "saved_files.csv").exists()
assert not list(OUTPUT_DIR.rglob("*.sql"))
assert set(path.name for path in OUTPUT_DIR.iterdir()) == {"stages","extension_settings.json"}
print("Stage exports and final-cell storage checks passed")
'''))
            notebook = nbformat.v4.new_notebook(cells=cells)
            with patch.dict(os.environ,{"IPYTHONDIR":str(base/"ipython"),"JUPYTER_RUNTIME_DIR":str(base/"jupyter-runtime")}):
                executed = NotebookClient(notebook,kernel_name="python3",timeout=180).execute(cwd=str(base))
            artifact = Path("/tmp/decorrect-storage-test")
            artifact.mkdir(exist_ok=True)
            nbformat.write(executed,artifact/"executed.ipynb")
            output = base / "output_decorrect_notebook"
            self.assertFalse((output/"snapshots").exists())
            self.assertFalse((output/"saved_files.csv").exists())
            self.assertEqual(len(pd.read_parquet(output/"stages/15_ADI_FINAL.parquet")),3)
            config = json.loads((output/"extension_settings.json").read_text())
            self.assertEqual(config["cpe_options"]["span_mode"],"OVO3_38P_F2F")


if __name__ == "__main__":
    unittest.main()
