"""Synthetic mixed/outer/unchanged shot validation against full native CPE refits."""
import ast
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
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
    index = next(i for i, c in enumerate(cells) if c["cell_type"] == "markdown" and c["source"].startswith(f"## {number}." if number >= 10 else f"## {number:02d}."))
    return cells[index+1]["source"]


def reference():
    namespace = {"pd": pd, "np": np, "dataclass": dataclass}
    doc = json.loads(MAIN.read_text())
    for number in range(22, 27):
        exec(section(doc, number), namespace)
    options = dict(span_mode=namespace["SPAN_MODE"], min_points_guide=namespace["MIN_POINTS_GUIDE"], eval_grid_n=namespace["CPE_EVAL_GRID_N"],
                   ridge_regression=True, gopt_spec=.95, gopt_tolerance=.001, gopt_type=1, use_span_box_constraint=True)
    namespace["G_OPT_SPEC"] = .95
    namespace["SPAN_TOLERANCE"] = .012
    namespace["RIDGE_VALVE_HYPER"]["RK7"] = .7  # verify saved custom settings, not bundled defaults
    settings = dict(cpe_options=options, use_virtual_chip_points=True, virtual_wafer_radius_um=144000., span_tolerance=.012, minimum_ridge=namespace["MINIMUM_RIDGE"],
                    add_ridge=namespace["ADD_RIDGE"], max_gopt_return=namespace["MAX_GOPT_RETURN"], max_span_iter=namespace["MAX_SPAN_ITER"], cd_tol=namespace["CD_TOL"],
                    ridge_valves=namespace["RIDGE_VALVE_HYPER"], active_span_limits=namespace["get_active_span_limits"](options["span_mode"]))
    return namespace, settings


def fixture(namespace, settings, no_outer=False):
    rng = np.random.default_rng(20261027)
    frames = []
    cases = [("A", 11, 0., 0., "center"), ("A", 11, 140000., 0., "mixed"), ("A", 12, 0., 0., "center"), ("A", 12, 145000., 0., "outer"), ("B", 9, 0., 0., "center")]
    for lot, wafer, cx, cy, kind in cases:
        if no_outer and kind != "center":
            continue
        count = 40
        rx = rng.uniform(-7000, 6500, count) if kind != "outer" else rng.uniform(0, 800, count)
        ry = rng.uniform(-5000, 5000, count) if kind != "outer" else rng.uniform(-1000, 1000, count)
        if kind == "mixed":
            rx[:3], ry[:3] = [-6000., 4000., 6000.], [0., 0., 0.]
        radius = np.hypot(cx + rx, cy + ry)
        outer = radius > 144000.
        frame = pd.DataFrame(dict(LOT_ID=lot, Wafer=wafer, fcp_x=cx, fcp_y=cy, coordinate_X=rx, coordinate_Y=ry, radius=radius,
                                  DieX=int(cx/1000), DieY=0, TEST=np.arange(81,81+count), GROUP="E2", STEP_PITCH_X=20000., STEP_PITCH_Y=20000., CHIP_X_NUM=2, CHIP_Y_NUM=2))
        frame["photo_transn_seq"] = pd.Series([9007199254741003 + wafer]*count, dtype="Int64")
        frame["measurement_scale"] = np.where(outer, .5, 1.)
        frame["measurement_source"] = np.where(outer, "oco_edge", "oco_main")
        for axis, intercept in [("x", .003), ("y", -.002)]:
            original = intercept + 2e-8*rx - 3e-8*ry + 1e-12*rx*ry + rng.normal(0,.00015,count)
            frame[f"{axis.upper()}_reg_original"] = original
            frame[f"{axis.upper()}_reg"] = original * frame.measurement_scale
            frame[f"mrc_fit_{axis}"], frame[f"psm_fit_{axis}"] = .00012, .00009
            frame[f"wk_fit_{axis}"] = .0003 + cx * 1e-10
            frame[f"rk_fit_{axis}"] = rx * 1e-9
            frame[f"total_fit_{axis}"] = frame[f"wk_fit_{axis}"] + frame[f"rk_fit_{axis}"]
            frame[f"raw_{axis}"] = frame[f"{axis.upper()}_reg"] - frame[f"mrc_fit_{axis}"] - frame[f"psm_fit_{axis}"]
            frame[f"raw_minus_total_fit_{axis}"] = frame[f"raw_{axis}"] - frame[f"total_fit_{axis}"]
        frames.append(frame)
    base = pd.concat(frames, ignore_index=True)
    fitted, _, _ = namespace["run_cpe38_vba_style_shotwise"](base, label="BASE", **settings["cpe_options"])
    return fitted


class SweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference, cls.settings = reference()
        cls.base = fixture(cls.reference, cls.settings)
        cls.doc = json.loads((HERE / "OCO_Edge_Sweep_29_34.ipynb").read_text())

    def namespace(self):
        ns = {"np": np, "pd": pd, "ES_RADIUS_UM": 144000., "ES_METRIC_AXES": ["x", "y"], "ES_STD_DDOF": 1}
        ns["ES_WAFER_KEYS"], ns["ES_SHOT_KEYS"] = ["LOT_ID","Wafer"], ["LOT_ID","Wafer","fcp_x","fcp_y"]
        for num in [29, 32]:
            nodes = [n for n in ast.parse(section(self.doc, num)).body if isinstance(n, ast.FunctionDef)]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), "functions", "exec"), ns)
        ns["ES_FILTERS"] = {}
        return ns

    def test_abs_mean_sample_sigma_boundary_and_empty_inner(self):
        ns = self.namespace()
        frame = pd.DataFrame({"LOT_ID": ["A"]*4, "Wafer": [11]*4, "radius": [144000.,143000.,145000.,146000.],
                              "metric_residual_x": [-.001,-.003,.002,.004], "metric_residual_y": [.001,.003,-.002,-.004],
                              "real_residual_x": [9.]*4, "real_residual_y": [9.]*4})
        metrics = ns["es_metric_table"](frame, ["LOT_ID", "Wafer"], .5)
        x = metrics[metrics.axis.eq("x")]
        inner = x[x.region.eq("R_LE_144MM")].iloc[0]
        self.assertEqual(inner.n_valid, 2)
        self.assertAlmostEqual(inner.abs_mean_nm, 2.)
        self.assertAlmostEqual(inner.M3S_nm, 2. + 3*np.sqrt(2))
        allpoints = x[x.region.eq("ALL_POINTS")].iloc[0]
        self.assertAlmostEqual(allpoints.abs_mean_nm, .5)
        self.assertAlmostEqual(allpoints.M3S_nm, .5+3*np.std([-1,-3,2,4],ddof=1))
        only_outer = frame.assign(radius=145000.)
        result = ns["es_metric_table"](only_outer, ["LOT_ID","Wafer"], .5)
        self.assertTrue(result.loc[result.region.eq("R_LE_144MM"), "M3S_nm"].isna().all())
        self.assertTrue(result.loc[result.region.eq("R_LE_144MM"), "n_valid"].eq(0).all())

    def test_fixed_correction_update_and_full_refit_equivalence(self):
        ns = self.namespace()
        base = ns["es_prepare_points"](self.base)
        original = base.copy(deep=True)
        for scale in [i/10 for i in range(1,11)]:
            changed = ns["es_scaled_input"](base, scale)
            for axis in ["x","y"]:
                target_reg = np.where(base._es_outer, scale*base[f"{axis.upper()}_reg_original"], base[f"{axis.upper()}_reg"])
                expected = target_reg - base[f"mrc_fit_{axis}"] - base[f"psm_fit_{axis}"] - base[f"total_fit_{axis}"]
                np.testing.assert_allclose(changed[f"raw_minus_total_fit_{axis}"], expected, rtol=0, atol=1e-17)
                np.testing.assert_array_equal(changed[f"wk_fit_{axis}"], base[f"wk_fit_{axis}"])
                np.testing.assert_array_equal(changed[f"rk_fit_{axis}"], base[f"rk_fit_{axis}"])
            full, _, _ = self.reference["run_cpe38_vba_style_shotwise"](changed, label="FULL", **self.settings["cpe_options"])
            affected, _, _ = self.reference["run_cpe38_vba_style_shotwise"](changed.loc[changed._es_affected], label="AFFECTED", **self.settings["cpe_options"])
            combined = base.copy()
            for col in ["real_residual_x","real_residual_y"]:
                combined.loc[affected.index,col] = affected[col]
                np.testing.assert_allclose(combined[col], full[col], rtol=0, atol=1e-15, equal_nan=True)
            evaluated = ns["es_evaluate_original_measurement"](affected)
            for axis in ["x","y"]:
                rows = base.loc[affected.index]
                # Independent physical target: original DB measurement minus fixed corrections and the new CPE.
                unscaled = rows[f"{axis.upper()}_reg_original"] - rows[f"mrc_fit_{axis}"] - rows[f"psm_fit_{axis}"] - rows[f"total_fit_{axis}"]
                np.testing.assert_allclose(evaluated[f"metric_input_{axis}"],unscaled,rtol=0,atol=1e-17)
                np.testing.assert_allclose(evaluated[f"metric_residual_{axis}"],unscaled-affected[f"CPE_fit_{axis}"],rtol=0,atol=1e-17,equal_nan=True)
                inner = ~affected._es_outer
                np.testing.assert_array_equal(evaluated.loc[inner,f"metric_residual_{axis}"],affected.loc[inner,f"real_residual_{axis}"])
                if scale == 1.:
                    np.testing.assert_array_equal(evaluated[f"metric_residual_{axis}"],affected[f"real_residual_{axis}"])
                else:
                    self.assertGreater(np.nanmax(np.abs(evaluated[f"metric_residual_{axis}"]-affected[f"real_residual_{axis}"])),1e-6)
        pd.testing.assert_frame_equal(base, original)

    def test_known_original_measurement_is_restored_without_scaling_cpe(self):
        ns = self.namespace()
        frame = pd.DataFrame({"_es_outer":[True,False],"measurement_scale":[.5,1.],"X_reg_original":[.010,.010],"Y_reg_original":[-.010,-.010],
                              "raw_minus_total_fit_x":[.0035,.0085],"raw_minus_total_fit_y":[-.0035,-.0085],
                              "CPE_fit_x":[.003,.003],"CPE_fit_y":[-.003,-.003]},index=[4,9])
        evaluated = ns["es_evaluate_original_measurement"](frame)
        np.testing.assert_allclose(evaluated.metric_residual_x,[.0055,.0055],rtol=0,atol=1e-18)
        np.testing.assert_allclose(evaluated.metric_residual_y,[-.0055,-.0055],rtol=0,atol=1e-18)
        pd.testing.assert_series_equal(evaluated.CPE_fit_x,frame.CPE_fit_x)
        pd.testing.assert_series_equal(evaluated.CPE_fit_y,frame.CPE_fit_y)

    def test_baseline_mismatch_stops_and_full_excel_fallback_ignores_samples(self):
        ns = self.namespace()
        with tempfile.TemporaryDirectory(prefix="sweep-read-") as temp:
            folder = Path(temp)
            stages = folder/"stages"
            stages.mkdir()
            ns.update(ES_INPUT_DIR=folder,ES_OUTPUT_DIR=folder,ES_BASELINE_ATOL_UM=1e-9)
            sample = stages/"ONLY_SAMPLE_sample_2.xlsx"
            self.base.head(2).to_excel(sample,index=False)
            with self.assertRaises(FileNotFoundError):
                ns["es_read_full"]("ONLY_SAMPLE")
            (stages/"FULL.parquet").write_bytes(b"bad parquet")
            self.base.head(5).to_excel(stages/"FULL.xlsx",index=False)
            frame,path=ns["es_read_full"]("FULL")
            self.assertEqual(len(frame),5)
            self.assertEqual(path.suffix,".xlsx")
            self.assertTrue(ns["es_assert_baseline"](self.base,self.base).passed.all())
            bad=self.base.copy()
            bad.loc[bad.index[0],"CPE_fit_x"]+=.0001
            with self.assertRaises(ValueError):
                ns["es_assert_baseline"](bad,self.base)
            self.assertTrue((folder/"Baseline_Parity_Failed.xlsx").is_file())

    def run_kernel(self, base, output_name):
        with tempfile.TemporaryDirectory(prefix="edge-sweep-") as temp:
            folder = Path(temp)
            stages = folder / "output_decorrect_notebook/stages"
            stages.mkdir(parents=True)
            point_path = stages / "27_OCO_FINAL_POINTS.parquet"
            base.to_parquet(point_path,index=False)
            input_bytes = point_path.read_bytes()
            (stages.parent/"extension_settings.json").write_text(json.dumps(self.settings))
            notebook = nbformat.read(HERE / "OCO_Edge_Sweep_29_34.ipynb",as_version=4)
            index32 = next(i for i,c in enumerate(notebook.cells) if c.cell_type=="code" and c.id=="edge-sweep-32")
            notebook.cells.insert(index32, nbformat.v4.new_code_cell('''
es_native_run = es_run_cpe38_vba_style_shotwise
es_calls = []
def es_spy(frame, **kwargs):
    es_calls.append(frame[ES_SHOT_KEYS].drop_duplicates())
    return es_native_run(frame, **kwargs)
es_run_cpe38_vba_style_shotwise = es_spy
'''))
            notebook.cells.append(nbformat.v4.new_code_cell('''
assert es_baseline_parity.passed.all()
assert all(set(call.fcp_x).issubset({140000.,145000.}) for call in es_calls)
assert ES_SCALES == [i/10 for i in range(1,11)]
assert len(es_calls) == (len(ES_SCALES) if len(es_shot_index) else 0)
assert ES_RIDGE_VALVE_HYPER["RK7"] == .7
assert ES_SPAN_TOLERANCE == .012
assert (ES_OUTPUT_DIR / "OCO_Edge_Scale_Sweep.xlsx").is_file()
assert len(es_wafer_metrics) == len(es_wafer_index)*len(ES_SCALES)*2*2
assert es_wafer_metrics.metric_basis.eq("UNSCALED_MEASUREMENT").all()
if len(es_shot_index):
    assert len(es_shot_index) == 2
    assert es_shot_metrics.loc[es_shot_metrics.fcp_x.eq(145000.) & es_shot_metrics.region.eq("R_LE_144MM"), "M3S_nm"].isna().all()
    mixed = es_shot_metrics[es_shot_metrics.fcp_x.eq(140000.) & es_shot_metrics.axis.eq("x") & es_shot_metrics.region.eq("R_LE_144MM")]
    assert mixed.M3S_nm.max()-mixed.M3S_nm.min() > 1e-7
    unchanged = es_wafer_metrics[es_wafer_metrics.LOT_ID.eq("B")]
    assert unchanged.groupby(["axis","region"]).M3S_nm.nunique().eq(1).all()
    assert len(list((ES_OUTPUT_DIR/"points").glob("*.parquet"))) == len(ES_SCALES)
    for scale in ES_SCALES:
        saved = pd.read_parquet(ES_OUTPUT_DIR/"points"/f"Affected_points_scale_{int(round(scale*100)):03d}.parquet")
        baseline = es_affected_base.reset_index(drop=True)
        outer = saved.radius.gt(ES_RADIUS_UM)
        for axis in ["x","y"]:
            unscaled_input = baseline[f"raw_minus_total_fit_{axis}"].copy()
            unscaled_input.loc[outer] += (1.-baseline.loc[outer,"measurement_scale"])*baseline.loc[outer,f"{axis.upper()}_reg_original"]
            expected = unscaled_input-saved[f"CPE_fit_{axis}"]
            np.testing.assert_allclose(saved[f"metric_residual_{axis}"],expected,rtol=0,atol=1e-17,equal_nan=True)
            for region,mask in [("R_LE_144MM",~outer),("ALL_POINTS",pd.Series(True,index=saved.index))]:
                for key,rows in saved.loc[mask].groupby(ES_SHOT_KEYS,observed=True):
                    values=expected.loc[rows.index]*1000
                    direct=abs(values.mean())+3*values.std(ddof=ES_STD_DDOF)
                    selected=es_shot_metrics.axis.eq(axis)&es_shot_metrics.region.eq(region)&es_shot_metrics.scale.eq(scale)
                    for col,value in zip(ES_SHOT_KEYS,key):
                        selected &= es_shot_metrics[col].eq(value)
                    assert np.isclose(es_shot_metrics.loc[selected,"M3S_nm"].iloc[0],direct,rtol=0,atol=1e-12,equal_nan=True)
        if scale == 1.:
            np.testing.assert_array_equal(saved.metric_residual_x,saved.real_residual_x)
        else:
            assert (saved.loc[outer,"metric_residual_x"]-saved.loc[outer,"real_residual_x"]).abs().max()>1e-6
else:
    assert es_shot_metrics.empty
    assert es_wafer_metrics.groupby(["LOT_ID","Wafer","axis","region"]).M3S_nm.nunique().eq(1).all()
'''))
            with patch.dict(os.environ,{"IPYTHONDIR":str(folder/"ipython"),"JUPYTER_RUNTIME_DIR":str(folder/"runtime")}):
                executed = NotebookClient(notebook,kernel_name="python3",timeout=240).execute(cwd=str(folder))
            self.assertEqual(point_path.read_bytes(),input_bytes)
            output = folder/"output_oco_edge_scale_sweep"
            report = pd.read_excel(output/"OCO_Edge_Scale_Sweep.xlsx",sheet_name=None)
            self.assertIn("Wafer_M3S",report)
            self.assertIn("Affected_shot_M3S",report)
            self.assertTrue(report["Baseline_parity"].passed.all())
            self.assertGreaterEqual(len(list((output/"plots").glob("*.png"))),4)
            artifact = Path("/tmp/edge-scale-sweep-tests")/output_name
            artifact.mkdir(parents=True,exist_ok=True)
            nbformat.write(executed,artifact/"executed.ipynb")
            for path in output.glob("*.xlsx"):
                (artifact/path.name).write_bytes(path.read_bytes())
            for path in (output/"plots").glob("*.png"):
                (artifact/path.name).write_bytes(path.read_bytes())

    def test_actual_kernel_metrics_affected_shots_exports_and_saved_settings(self):
        self.run_kernel(self.base,"mixed_outer")

    def test_actual_kernel_no_outer_points(self):
        self.run_kernel(fixture(self.reference,self.settings,no_outer=True),"no_outer")

    def test_full_prefix_unchanged_and_cells_compile(self):
        original=nbformat.read(MAIN,as_version=4)
        full=nbformat.read(HERE/"MRC_PSM_decorrect_Edge_Sweep.ipynb",as_version=4)
        stop=next(i for i,c in enumerate(original.cells) if c.cell_type=="markdown" and c.source.startswith("## 29."))
        self.assertEqual(original.cells[:stop],full.cells[:stop])
        for path in [HERE/"OCO_Edge_Sweep_29_34.ipynb",HERE/"MRC_PSM_decorrect_Edge_Sweep.ipynb"]:
            notebook=nbformat.read(path,as_version=4)
            nbformat.validate(notebook)
            for c in notebook.cells:
                if c.cell_type=="code":
                    compile(c.source,c.id,"exec")
                    self.assertLess(len(c.source.splitlines()),1000)
                    self.assertFalse(c.outputs)


if __name__ == "__main__":
    unittest.main()
