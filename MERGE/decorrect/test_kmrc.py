"""Known coefficient truth and real-kernel single/split-step K-MRC validation."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd

from .test_oco_edge import MAIN, HERE, PHOTO, fixtures, definitions, section, MOCK_DB


class KMRCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(MAIN.read_text())
        cls.ns = {"np": np, "pd": pd, "dataclass": dataclass}
        common = next(c["source"] for c in cls.doc["cells"] if c["cell_type"] == "code" and "def integer(" in c["source"])
        definitions(common, cls.ns)
        definitions(section(cls.doc, 15), cls.ns)
        exec(section(cls.doc, 20), cls.ns)

    def points(self, n, seed, bx, by, wafer=11):
        rng = np.random.default_rng(seed)
        frame = pd.DataFrame({"LOT_ID": "LOT_A", "Wafer": wafer, "fcp_x": rng.integers(-5, 6, n) * 20000.,
                              "fcp_y": rng.integers(-5, 6, n) * 20000., "coordinate_X": rng.uniform(-5000, 5000, n), "coordinate_Y": rng.uniform(-5000, 5000, n)})
        frame.loc[0, ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]] = [140000., 0., 6000., 0.]
        mx, my = self.ns["osr_wk20p_rk20p"](*(frame[c].to_numpy(float) for c in ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]))
        self.assertEqual(np.linalg.matrix_rank(mx), 19)
        self.assertEqual(np.linalg.matrix_rank(my), 19)
        frame["raw_x"], frame["raw_y"] = mx @ bx, my @ by
        return frame, mx, my

    def test_known_beta_difference_sign_and_evaluation_at_different_points(self):
        rng = np.random.default_rng(1900)
        a, ay, delta, dy, remain, remain_y = [rng.normal(0, .002, 19) for _ in range(6)]
        adi, _, _ = self.points(130, 1, a, ay)
        e1, _, _ = self.points(110, 2, a + delta, ay + dy)
        target, mx, my = self.points(90, 3, delta + remain, dy + remain_y)
        fit = self.ns["run_company_joint_regression"]
        _, ca, sa = fit(adi, label="ADI")
        _, ce, se = fit(e1, label="E1")
        result, coeff, diag, excluded = self.ns["apply_kmrc_difference"](target, ca, ce, sa, se)
        self.assertTrue(excluded.empty)
        self.assertEqual(diag.n_adi_valid.iloc[0], 130)  # outer ADI point retained
        xcols = [f"{k}_X" for k in self.ns["COEFF_KEYS_DX"]]
        ycols = [f"{k}_Y" for k in self.ns["COEFF_KEYS_DY"]]
        np.testing.assert_allclose(coeff[xcols].iloc[0], delta, rtol=1e-6, atol=1e-9)
        np.testing.assert_allclose(coeff[ycols].iloc[0], dy, rtol=1e-6, atol=1e-9)
        np.testing.assert_allclose(result.total_fit_x, mx @ delta, rtol=1e-6, atol=1e-11)
        np.testing.assert_allclose(result.raw_minus_total_fit_x, mx @ remain, rtol=1e-6, atol=1e-11)
        np.testing.assert_allclose(result.raw_minus_total_fit_y, my @ remain_y, rtol=1e-6, atol=1e-11)
        self.assertGreater(np.linalg.norm(result.raw_minus_total_fit_x), .001)  # not E2's own regression removal

    def test_single_step_radius_is_only_for_main_e1_and_adi_is_unrestricted(self):
        frame = pd.DataFrame({"LOT_ID": ["A"]*8, "Wafer": [11]*8,
                              "GROUP": pd.Categorical(["E1"]*4 + ["E2"]*2 + ["E1", "E2"], categories=["E1", "E2", "E3"]),
                              "measurement_source": ["oco_main"]*6 + ["oco_edge"]*2,
                              "radius": [143999., 144000., 144001., 146500., 100000., 146500., 130000., 146500.]})
        cfg = SimpleNamespace(target_mstepseq_oco="VC077251", target_mstepseq_oco_edge="VC077251", include_oco_edge=True, kmrc_e1_radius_um=144000.)
        select = self.ns["select_oco_model_inputs"]
        analysis, ref, count = select(frame, cfg)
        self.assertEqual(ref.index.tolist(), [0, 1])
        self.assertEqual(analysis.index.tolist(), [4, 5])
        self.assertEqual(count.n_e1_main_before_radius.iloc[0], 4)
        cfg.target_mstepseq_oco_edge = "VC077252"
        analysis, ref, _ = select(frame, cfg)
        self.assertEqual(ref.index.tolist(), [0, 1, 2, 3])
        self.assertEqual(analysis.index.tolist(), [4, 5, 7])
        cfg.target_mstepseq_oco = cfg.target_mstepseq_oco_edge = "VC075251"
        analysis, ref, _ = select(frame, cfg)
        self.assertEqual(ref.index.tolist(), [0, 1])
        self.assertEqual(analysis.index.tolist(), [0, 1, 2, 3])

    def test_missing_sources_exclude_wafer_and_all_empty_is_supported(self):
        beta = np.full(19, .001)
        adi, _, _ = self.points(40, 5, beta, beta)
        e1, _, _ = self.points(40, 6, beta * 2, beta * 2)
        target = pd.concat([adi.assign(Wafer=w) for w in [11, 12, 13]], ignore_index=True)
        _, ca, sa = self.ns["run_company_joint_regression"](adi)
        _, ce, se = self.ns["run_company_joint_regression"](e1)
        result, coeff, diag, excluded = self.ns["apply_kmrc_difference"](target, ca, ce, sa, se)
        self.assertEqual(set(result.Wafer), {11})
        self.assertEqual(set(excluded.Wafer), {12, 13})
        self.assertEqual(diag.status.eq("excluded").sum(), 2)
        empty, co, di, ex = self.ns["apply_kmrc_difference"](target, ca.iloc[:0], ce.iloc[:0], sa, se)
        self.assertTrue(empty.empty and co.empty)
        self.assertEqual(len(ex), len(target))
        self.assertIn("raw_minus_total_fit_x", empty)

    def test_actual_kernel_single_step_077_non077_and_missing_references(self):
        for mode in os.environ.get("KMRC_TEST_MODES", "077,non077,all_missing").split(","):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix=f"kmrc-{mode}-") as temp:
                base = Path(temp)
                data = fixtures()
                raw = data["raw"]
                # A full 147-mm single step: append outer main measurements and shift local marks.
                local = raw.data_kind.eq("TESTDATA") & raw.lot_transn_seq.isin([101, 201])
                raw.loc[local, "value_x"] += 6000.
                outer = raw[raw.lot_transn_seq.eq(201) & raw.data_kind.eq("RAWDATA") & raw.coordinate_x.eq(0) & raw.coordinate_y.eq(0)].copy()
                outer["coordinate_x"], outer["coordinate_y"] = 7., 0.
                raw = pd.concat([raw, outer], ignore_index=True)
                if mode != "077":
                    missing = [12] if mode == "non077" else [11, 12]
                    remove = raw.lot_transn_seq.eq(201) & raw.slot_id.isin(missing) & raw.data_kind.eq("RAWDATA") & raw.test_point_no.between(1, 80) & raw.coordinate_x.ne(7)
                    raw = raw[~remove].copy()
                    data["lot_main"]["mstepseq"] = "VC075251"
                data["raw"] = raw
                fixture_dir = base / "fixture"
                fixture_dir.mkdir()
                for name, frame in data.items():
                    frame.to_parquet(fixture_dir / f"{name}.parquet", index=False)
                notebook = nbformat.read(MAIN, as_version=4)
                stop = next(i for i, c in enumerate(notebook.cells) if c.cell_type == "markdown" and c.source.startswith("## 29."))
                notebook.cells = notebook.cells[:stop]
                setup = next(c for c in notebook.cells if c.cell_type == "code" and "class PipelineConfig:" in c.source)
                step = "VC077251" if mode == "077" else "VC075251"
                setup.source = setup.source.replace("cfg.reference_date = None", 'cfg.reference_date = "2026-10-23"').replace("EXCEL_PREVIEW_ROWS = 10000", "EXCEL_PREVIEW_ROWS = 500").replace("PREVIEW_ROWS = 10", "PREVIEW_ROWS = 2")
                setup.source += f'\ncfg.target_mstepseq_oco = {step!r}\ncfg.target_mstepseq_oco_edge = {step!r}\n'
                notebook.cells.insert(notebook.cells.index(setup) + 1, nbformat.v4.new_code_cell(MOCK_DB))
                check = f'''mode = {mode!r}
assert not OCO_SPLIT_STEPS
assert cfg.oco_edge_scale == .5
assert not any("'VC077252'" in sql for sql in query_calls)
assert sum("apc_nautil_dat_rawdata" in sql for sql in query_calls) == 2
assert df_final_oco.measurement_scale.eq(1.).all()
assert df_oco_e1_raw.radius.le(144000).all()
assert df_adi_reg.radius.gt(144000).any()
assert df_adi_reg.shape[0] == 56
assert set(df_oco_model_input_counts.n_e1_main_before_radius) == ({{28}} if mode == "077" else {{4,28}} if mode == "non077" else {{4}})
assert df_final_oco.radius.gt(144000).any()
assert df_final_oco.GROUP.eq("E2" if mode == "077" else "E1").all()
expected = {{11,12}} if mode == "077" else {{11}} if mode == "non077" else set()
assert set(df_oco_reg.Wafer) == expected
assert set(df_oco_cpe.Wafer) == expected
assert set(df_wk_rk_diag_oco.loc[df_wk_rk_diag_oco.status.eq("excluded"), "Wafer"]) == ({{11,12}} - expected)
assert len(df_oco_kmrc_excluded) == len(df_final_oco) - len(df_oco_reg)
if len(df_oco_reg):
    assert df_oco_reg.radius.gt(144000).any()
    joined = coef_oco.merge(coef_oco_e1, on=["LOT_ID","Wafer"], suffixes=("_delta","_e1")).merge(coef_adi, on=["LOT_ID","Wafer"])
    for names, axis in [(COEFF_KEYS_DX,"X"),(COEFF_KEYS_DY,"Y")]:
        for term in names:
            col = f"{{term}}_{{axis}}"
            np.testing.assert_allclose(joined[col+"_delta"], joined[col+"_e1"] - joined[col])
    assert df_decomposition_check.loc[df_decomposition_check["mode"].eq("OCO"), "passed"].all()
else:
    assert df_decomposition_check.loc[df_decomposition_check["mode"].eq("OCO"), "n_checked"].eq(0).all()
assert extension_settings["kmrc_adi_radius_limit_um"] is None
assert extension_settings["kmrc_definition"] == "OCO_E1_RAW_MINUS_ADI_RAW"
assert "DieX" in pd.read_parquet(STAGE_DIR / "28_OCO_FINAL_SHOT_DATA.parquet")
print("Single-step K-MRC passed", mode)
'''
                notebook.cells.append(nbformat.v4.new_code_cell(check))
                with patch.dict(os.environ, {"IPYTHONDIR": str(base / "ipython"), "JUPYTER_RUNTIME_DIR": str(base / "runtime")}):
                    executed = NotebookClient(notebook, kernel_name="python3", timeout=240).execute(cwd=str(base))
                artifact = Path("/tmp/kmrc-tests")
                artifact.mkdir(exist_ok=True)
                nbformat.write(executed, artifact / f"{mode}.ipynb")


if __name__ == "__main__":
    unittest.main()
