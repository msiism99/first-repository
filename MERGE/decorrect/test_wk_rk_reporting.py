"""Regression tests for real wafer/shot reporting; no production data or DB access."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / "MRC_PSM_decorrect.ipynb"


def section(document, number):
    cells = document["cells"]
    i = next(i for i, c in enumerate(cells) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number:02d}."))
    return cells[i + 1]["source"]


def functions(source, namespace):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "notebook-functions", "exec"), namespace)


def fixture():
    rng = np.random.default_rng(123)
    rows = []
    for lot, wafer in [("A", 11), ("A", 12), ("B", 9), ("B", 10), ("B", 14)]:
        for dx, dy in [(0, 0), (7, 0), (-7, 0), (0, 7), (0, -7)]:
            for test in range(8):
                rx, ry = rng.uniform(-1000, 1000, 2)
                rows.append(dict(LOT_ID=lot, Wafer=wafer, fcp_x=dx * 20000., fcp_y=dy * 20000., DieX=dx, DieY=dy,
                                 STEP_PITCH_X=20000., STEP_PITCH_Y=20000., MAP_SHIFT_X=0., MAP_SHIFT_Y=0.,
                                 coordinate_X=rx, coordinate_Y=ry, raw_x=.001 + .0003 * dx + rng.normal(0, .0001),
                                 raw_y=-.001 + .0002 * dy + rng.normal(0, .0001), TEST=test + 1))
    frame = pd.DataFrame(rows)
    frame["LOT_ID"] = pd.Categorical(frame["LOT_ID"], categories=["A", "B", "UNUSED"])
    frame["Wafer"] = pd.Categorical(frame["Wafer"], categories=[9, 10, 11, 12, 14, 99])
    for col in ["fcp_x", "fcp_y"]:
        frame[col] = pd.Categorical(frame[col], categories=[-140000., 0., 140000., 300000.])
    return frame


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(MAIN.read_text())
        cls.ns = {"np": np, "pd": pd, "WAFER_KEYS": ["LOT_ID", "Wafer"], "SHOT_KEYS": ["LOT_ID", "Wafer", "fcp_x", "fcp_y"]}
        common = next(c["source"] for c in cls.document["cells"] if c["cell_type"] == "code" and "def integer(" in c["source"])
        functions(common, cls.ns)
        functions(section(cls.document, 18), cls.ns)
        exec(section(cls.document, 20), cls.ns)

    def test_categorical_groups_exactly_match_measured_keys(self):
        f = fixture()
        summarize = self.ns["summarize_values"]
        wafer = summarize(f, ["LOT_ID", "Wafer"], ["raw_x"])
        self.assertEqual(set(wafer.loc[wafer.LOT_ID == "A", "Wafer"]), {11, 12})
        self.assertEqual(len(wafer), 5)
        shot = summarize(f, self.ns["SHOT_KEYS"], ["raw_x"])
        self.assertEqual(len(shot), 25)
        self.assertTrue(shot.n_points.eq(8).all())
        self.assertLessEqual(np.hypot(shot.fcp_x.astype(float), shot.fcp_y.astype(float)).max(), 150000.)
        self.assertEqual(shot.n_points.sum(), len(f))
        result = self.ns["attach_measured_shot_indices"](shot, f)
        self.assertTrue(result.shot_index_status.eq("ok").all())
        np.testing.assert_allclose(result.DieX.to_numpy(float) * 20000, result.fcp_x.to_numpy(float))
        # Missing keys and invalid measurements are real records, not empty categorical combinations.
        partial = f.iloc[:3].copy()
        partial.loc[partial.index[0], "LOT_ID"] = np.nan
        partial["raw_x"] = np.nan
        s = summarize(partial, self.ns["SHOT_KEYS"], ["raw_x"])
        self.assertEqual(s.n_points.sum(), 3)
        self.assertEqual(len(s), 2)
        self.assertTrue(s.raw_x_n_valid.eq(0).all())
        empty = summarize(f.iloc[:0], self.ns["SHOT_KEYS"], ["raw_x"])
        self.assertTrue(self.ns["attach_measured_shot_indices"](empty, f.iloc[:0]).empty)

    def test_indices_use_map_origin_and_preserve_measured_edge_shots(self):
        f = fixture().iloc[:8].copy()
        for col in ["fcp_x", "fcp_y"]:
            f[col] = f[col].astype(float)
        f["DieX"], f["DieY"] = 8, -2
        f["MAP_SHIFT_X"], f["MAP_SHIFT_Y"] = 500., -600.
        f["fcp_x"], f["fcp_y"] = 160500., -40600.
        f["coordinate_X"], f["coordinate_Y"] = -18000., 0.
        # Center outside 150 mm but measured local mark is inside: must retain it.
        self.assertLess(np.hypot(142500., -40600.), 150000.)
        shot = self.ns["summarize_values"](f, self.ns["SHOT_KEYS"], ["raw_x"])
        result = self.ns["attach_measured_shot_indices"](shot, f.drop(columns=["DieX", "DieY"]))
        self.assertEqual((result.DieX.iloc[0], result.DieY.iloc[0]), (8, -2))
        result = self.ns["attach_measured_shot_indices"](shot, f.drop(columns=["STEP_PITCH_X", "STEP_PITCH_Y"]))
        self.assertEqual(result.DieX.iloc[0], 8)
        f.loc[f.index[0], "DieX"] = 7
        with self.assertRaisesRegex(ValueError, "실측 index"):
            self.ns["attach_measured_shot_indices"](shot, f)
        with self.assertRaisesRegex(ValueError, "여러 DieX"):
            self.ns["attach_measured_shot_indices"](shot, f.drop(columns=["STEP_PITCH_X"]))
        missing = f.drop(columns=["DieX", "DieY", "STEP_PITCH_X", "STEP_PITCH_Y"])
        self.assertEqual(self.ns["attach_measured_shot_indices"](shot, missing).shot_index_status.iloc[0], "missing_geometry")

    def test_numeric_regression_unchanged_and_real_insufficient_wafer_retained(self):
        f = fixture()
        # Compare against the previous implementation on ordinary object/numeric keys.
        old_document = json.loads(subprocess.check_output(["git", "show", "4d1a91a:MERGE/MRC_PSM_decorrect.ipynb"], cwd=HERE).decode())
        old_ns = {"np": np, "pd": pd}
        exec(section(old_document, 20), old_ns)
        plain = f.copy()
        for col in plain.select_dtypes("category").columns:
            plain[col] = plain[col].astype(object)
        expected, coef0, diag0 = old_ns["run_company_joint_regression"](plain)
        result, coef1, diag1 = self.ns["run_company_joint_regression"](f)
        values = [c for c in result if c.startswith(("wk_fit", "rk_fit", "total_fit", "raw_minus"))]
        np.testing.assert_allclose(result[values].to_numpy(float), expected[values].to_numpy(float), rtol=0, atol=0)
        pd.testing.assert_frame_equal(coef0, coef1)
        pd.testing.assert_frame_equal(diag0, diag1)
        small, coeff, diag = self.ns["run_company_joint_regression"](f.iloc[:3])
        self.assertTrue(coeff.empty)
        self.assertEqual(len(diag), 1)
        self.assertEqual(diag.status.iloc[0], "skip_too_few_points")
        self.assertEqual(len(self.ns["summarize_values"](small, ["LOT_ID", "Wafer"], ["wk_fit_x"])), 1)

    def test_lot_selection_and_rawdata_use_exact_selected_wafers(self):
        ns = dict(self.ns)
        functions(section(self.document, 4), ns)
        functions(section(self.document, 6), ns)
        cfg = SimpleNamespace(reference_date="2026-10-23", days=8, exclude_recent_days=1, slot_min=9, slot_max=14)
        adi = pd.DataFrame([dict(lotid=lot, slotid=w, photo_transn_seq=photo, lot_transn_seq=history,
                                timestamp="2026-10-20", mstepseq="ADI") for lot, w, photo, history in [("A", 11, 100, 1), ("A", 12, 100, 1), ("B", 9, 200, 2), ("B", 14, 200, 2)]])
        oco = pd.concat([adi.assign(lot_transn_seq=lambda x: x.lot_transn_seq + 10), adi.iloc[[0]].assign(slotid=10)], ignore_index=True)
        selected, _, _ = ns["select_lot_pair"](adi, oco, cfg)
        self.assertEqual(set(selected.loc[selected.lotid == "A", "slotid"]), {11, 12})
        raw = pd.DataFrame([dict(lot_transn_seq=1, slot_id=w, data_kind="RAWDATA", transn_occur_date="2026-10-20 12:00:00") for w in [9, 10, 11, 12, 14]])
        retained = ns["latest_raw_batch"](raw, selected)
        self.assertEqual(set(retained.slot_id), {11, 12})

    def test_repair_notebook_real_kernel_parquet_excel_and_scope(self):
        notebook = nbformat.read(HERE / "WK_RK_20_21_Repair.ipynb", as_version=4)
        nbformat.validate(notebook)
        with tempfile.TemporaryDirectory(prefix="wk-rk-report-") as temp:
            base = Path(temp)
            stages = base / "output_decorrect_notebook/stages"
            stages.mkdir(parents=True)
            data = fixture()
            data.to_parquet(stages / "19_ADI_TROCS_ATTACHED.parquet", index=False)
            original_input = (stages / "19_ADI_TROCS_ATTACHED.parquet").read_bytes()
            data.to_excel(stages / "19_OCO_TROCS_ATTACHED.xlsx", index=False)
            selected = pd.DataFrame({"lotid": ["A", "A", "B", "B", "B", "C"], "slotid": [11, 12, 9, 10, 14, 13]})
            selected.to_parquet(stages / "04_LOTINFO_ADI_SELECTED.parquet", index=False)
            selected.to_excel(stages / "04_LOTINFO_OCO_SELECTED.xlsx", index=False)
            with patch.dict(os.environ, {"IPYTHONDIR": str(base / "ipython"), "JUPYTER_RUNTIME_DIR": str(base / "runtime")}):
                executed = NotebookClient(notebook, kernel_name="python3", timeout=180).execute(cwd=str(base))
            for mode in ["ADI", "OCO"]:
                wafer = pd.read_parquet(stages / f"21_{mode}_WK_RK_WAFER_DATA.parquet")
                shot = pd.read_excel(stages / f"21_{mode}_WK_RK_SHOT_DATA.xlsx")
                self.assertEqual(set(wafer.loc[wafer.LOT_ID == "A", "Wafer"]), {11, 12})
                self.assertEqual(len(shot), 25)
                self.assertTrue(shot.n_points.eq(8).all())
                self.assertFalse(shot[["DieX", "DieY"]].isna().any().any())
                scope = pd.read_excel(stages / f"21_{mode}_WK_RK_WAFER_SCOPE.xlsx")
                self.assertEqual(scope.loc[scope.LOT_ID == "C", "scope_status"].iloc[0], "selected_without_stage19_points")
            self.assertEqual((stages / "19_ADI_TROCS_ATTACHED.parquet").read_bytes(), original_input)
            artifact = Path("/tmp/wk-rk-report-test")
            artifact.mkdir(exist_ok=True)
            nbformat.write(executed, artifact / "executed.ipynb")
            shot.to_excel(artifact / "example_shot_data.xlsx", index=False)


if __name__ == "__main__":
    unittest.main()
