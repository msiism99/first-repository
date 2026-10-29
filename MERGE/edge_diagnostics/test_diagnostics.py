"""Known CPE field + edge-only offsets, reference identifiability, and standalone notebook exports."""
import ast
from dataclasses import dataclass
import copy
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


def code(document, number):
    return next(c["source"] for c in document["cells"] if c["cell_type"] == "code" and c["id"] == f"edge-comparison-{number}")


def namespace(document):
    ns = dict(np=np, pd=pd, Path=Path, copy=copy, json=json, dataclass=dataclass)
    ns.update(EP_AXES=["x", "y"], EP_STD_DDOF=1, EP_INNER_RADIUS_UM=144000., EP_MAX_RADIUS_UM=147000., EP_MIN_EXTRA_INNER_POINTS=2,
              EP_MAX_SCALED_CONDITION=1e6, EP_MAX_EDGE_NOISE_GAIN=5., EP_SVD_RCOND=1e-12, EP_RADIAL_BINS_MM=np.arange(140.,147.01,.5))
    ns["EP_WAFER_KEYS"] = ["product", "LOT_ID", "Wafer"]
    ns["EP_SHOT_KEYS"] = ns["EP_WAFER_KEYS"]+["fcp_x", "fcp_y"]
    for number in [2, 3, 1]:
        exec(code(document, number), ns)
    for number in [0, 4, 5]:
        functions = [node for node in ast.parse(code(document, number)).body if isinstance(node, ast.FunctionDef)]
        exec(compile(ast.Module(body=functions, type_ignores=[]), "functions", "exec"), ns)
    return ns


def settings_for(ns):
    return dict(kmrc_definition="OCO_E1_RAW_MINUS_ADI_RAW", use_virtual_chip_points=True, virtual_wafer_radius_um=144000.,
        span_tolerance=.012, minimum_ridge=.001, add_ridge=10., max_gopt_return=50, max_span_iter=5000, cd_tol=1e-6,
        ridge_valves=copy.deepcopy(ns["EP_RIDGE_VALVE_HYPER"]), active_span_limits=copy.deepcopy(ns["EP_RK_SPAN_LIMITS_OVO3_38P_F2F"]),
        cpe_options=dict(span_mode="OVO3_38P_F2F", min_points_guide=10, eval_grid_n=10, ridge_regression=False,
                         gopt_spec=1., gopt_tolerance=.001, gopt_type=1, use_span_box_constraint=False))


def fixture(edge_offset=.001, no_edge=False):
    rng = np.random.default_rng(20261029)
    frames = []
    for kind, center in [("good",138000.), ("sparse",138100.), ("outer",146000.), ("central",0.)]:
        if no_edge and kind != "central":
            continue
        n_inner = {"good":45,"sparse":8,"outer":0,"central":40}[kind]
        rx = rng.uniform(-6000,5600,n_inner)
        ry = rng.uniform(-5000,5000,n_inner)
        n_edge = 0 if kind=="central" else 10
        if n_edge:
            boundary = 144000.-center
            rx = np.r_[rx,rng.uniform(boundary+10,boundary+90,n_edge)]
            ry = np.r_[ry,rng.uniform(-100,100,n_edge)]
        radius = np.hypot(center+rx,ry)
        outer = radius > 144000.
        n = len(rx)
        frame = pd.DataFrame(dict(LOT_ID="SAME_LOT",Wafer=11,fcp_x=center,fcp_y=0.,coordinate_X=rx,coordinate_Y=ry,radius=radius,
                                  DieX=int(center//1000),DieY=0,STEP_PITCH_X=20000.,STEP_PITCH_Y=20000.,CHIP_X_NUM=2,CHIP_Y_NUM=2,TEST=np.arange(81,81+n),GROUP="E2"))
        frame["photo_transn_seq"] = pd.Series([9007199254741999]*n,dtype="Int64")
        frame["measurement_scale"] = np.where(outer,.5,1.)
        for axis, sign in [("x",1.),("y",-1.)]:
            field = sign*(.001+1e-8*rx-0.5e-8*ry)
            original = field+.0003+sign*outer*edge_offset
            frame[f"{axis.upper()}_reg_original"] = original
            frame[f"raw_minus_total_fit_{axis}"] = original*frame.measurement_scale-.0003
        frames.append(frame)
    return pd.concat(frames,ignore_index=True)


class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=json.loads((HERE/"OCO_Edge_Inner_Comparison.ipynb").read_text())

    def test_restore_original_boundary_stats_and_no_fake_shots(self):
        ns=namespace(self.document)
        source=fixture()
        source.loc[0,"radius"]=144000.
        source.loc[1,"radius"]=147000.
        source.loc[2,"radius"]=147001.
        source["LOT_ID"]=pd.Categorical(source.LOT_ID,categories=["SAME_LOT","NEVER_MEASURED"])
        points,audit=ns["ep_prepare_points"](source,"KGVM")
        self.assertEqual(audit["n_outside_radius"],1)
        self.assertEqual(points.loc[points.radius.eq(144000.),"region"].iloc[0],"INNER")
        self.assertEqual(points.loc[points.radius.eq(147000.),"region"].iloc[0],"EDGE")
        for axis in ["x","y"]:
            np.testing.assert_allclose(points[f"input100_{axis}"],points[f"{axis.upper()}_reg_original"]-.0003,rtol=0,atol=1e-18)
        stats=ns["ep_input_stats"](points,ns["EP_WAFER_KEYS"])
        self.assertEqual(set(stats.LOT_ID),{"SAME_LOT"})
        self.assertEqual(len(stats),4)
        x=points.loc[points.region.eq("EDGE"),"input100_x"]*1000
        row=stats.loc[stats.axis.eq("x")&stats.region.eq("EDGE")].iloc[0]
        self.assertAlmostEqual(row.M3S_nm,abs(x.mean())+3*x.std(ddof=1))
        invalid=source.copy()
        index=invalid.index[invalid.measurement_scale.eq(.5)][0]
        invalid.loc[index,["raw_minus_total_fit_x","raw_minus_total_fit_y","X_reg_original","Y_reg_original"]]=np.nan
        prepared,_=ns["ep_prepare_points"](invalid,"KGVM")
        self.assertEqual(int((~prepared._fit_valid).sum()),1)

    def test_known_edge_offset_and_edge_values_cannot_train_reference(self):
        ns=namespace(self.document)
        options=ns["ep_restore_settings"](settings_for(ns))
        coefficients=[]
        for offset in [0.,.001,.004]:
            points,_=ns["ep_prepare_points"](fixture(offset),"KGVM")
            result,diag,coef=ns["ep_fit_inner_reference"](points,options)
            good=diag.loc[diag.fcp_x.eq(138000.)]
            self.assertTrue(good.eligible.all(),good.to_string())
            for axis,sign in [("x",1.),("y",-1.)]:
                expected=result.loc[result.fcp_x.eq(138000.)&result.region.eq("EDGE"),f"edge_deviation_{axis}"]
                np.testing.assert_allclose(expected,sign*offset,rtol=0,atol=1e-12)
            coefficients.append(coef)
            self.assertTrue(diag.loc[diag.fcp_x.eq(138100.),"status"].str.contains("too_few_inner_points").all())
            self.assertTrue(diag.loc[diag.fcp_x.eq(146000.),"status"].str.contains("too_few_inner_points").all())
        pd.testing.assert_frame_equal(coefficients[0],coefficients[1])
        pd.testing.assert_frame_equal(coefficients[0],coefficients[2])

    def test_rank_and_noise_screening_do_not_report_zero_error(self):
        ns=namespace(self.document)
        options=ns["ep_restore_settings"](settings_for(ns))
        points,_=ns["ep_prepare_points"](fixture(),"KGVM")
        mask=points.fcp_x.eq(138000.)&points.region.eq("INNER")
        deficient=points.copy()
        deficient.loc[mask,"coordinate_X"]=0.
        result,diag,_=ns["ep_fit_inner_reference"](deficient,options)
        self.assertTrue(diag.loc[diag.fcp_x.eq(138000.),"status"].eq("inner_rank_deficient").all())
        self.assertTrue(result.edge_deviation_x.isna().all())
        ns["EP_MAX_EDGE_NOISE_GAIN"]=1e-6
        result,diag,_=ns["ep_fit_inner_reference"](points,options)
        self.assertTrue(diag.loc[diag.fcp_x.eq(138000.),"status"].str.contains("edge_prediction_noise_high").all())
        stats=ns["ep_prediction_stats"](result,ns["EP_WAFER_KEYS"])
        self.assertTrue(stats.RMSE_nm.isna().all())
        self.assertTrue(stats.coverage_fraction.eq(0).all())
        self.assertTrue(diag.loc[diag.fcp_x.eq(138000.),"candidate_edge_RMSE_nm"].notna().all())

    def test_saved_ridge_and_active_span_match_original_solver(self):
        ns=namespace(self.document)
        settings=settings_for(ns)
        settings["cpe_options"].update(ridge_regression=True,gopt_spec=.3,use_span_box_constraint=True)
        settings["span_tolerance"]=1e-6
        settings["ridge_valves"]["RK3"]=.7
        for name in settings["active_span_limits"]:
            if name not in ["RK1","RK2"]:
                settings["active_span_limits"][name]={"min":-1e-8,"max":1e-8}
        options=ns["ep_restore_settings"](settings)
        points,_=ns["ep_prepare_points"](fixture(),"KGVM")
        points["input100_x"] = .001+1e-6*points.coordinate_X
        _,diag,coef=ns["ep_fit_inner_reference"](points,options)
        actual=diag.loc[diag.fcp_x.eq(138000.)&diag.axis.eq("x")].iloc[0]
        self.assertGreater(actual.lambda_max,0.)
        self.assertEqual(actual.method,"ridge_gopt_box_cd")
        native=dict(np=np,pd=pd,dataclass=dataclass)
        original=json.loads((HERE.parent/"MRC_PSM_decorrect.ipynb").read_text())
        for number in range(22,26):
            index=next(i for i,c in enumerate(original["cells"]) if c["cell_type"]=="markdown" and c["source"].startswith(f"## {number}."))
            exec(original["cells"][index+1]["source"],native)
        for name in list(native):
            if name.isupper() and "EP_"+name in ns:
                native[name]=copy.deepcopy(ns["EP_"+name])
        shot=points.loc[points.fcp_x.eq(138000.)&points._fit_valid]
        inner=shot.loc[shot.region.eq("INNER")]
        vx,vy,_,_,n_virtual=native["get_virtual_points_for_group"](shot,shot.coordinate_X,shot.coordinate_Y,fcp_x=138000.,fcp_y=0.,wafer_radius=144000.)
        fit=native["solve_vba_style_ridge_one_axis"](X_fit=native["cpe_38para"](inner.coordinate_X,inner.coordinate_Y)[0],y=inner.input100_x.to_numpy(),
            X_eval=native["cpe_38para"](vx,vy)[0],coeff_names=native["CPE38_KEYS_DX"],span_limits=settings["active_span_limits"],ridge_regression=True,
            gopt_spec=.3,gopt_tolerance=.001,minimum_ridge=settings["minimum_ridge"],add_ridge=settings["add_ridge"],max_gopt_return=settings["max_gopt_return"],
            gopt_type=1,inner_or_partial=native["determine_inner_or_partial"](len(inner),n_virtual),use_span_box_constraint=True,span_tolerance=1e-6,
            cd_tol=settings["cd_tol"],max_span_iter=settings["max_span_iter"],base_lambda_scale=native["choose_base_lambda_scale"](len(inner)))
        row=coef.loc[coef.fcp_x.eq(138000.)&coef.axis.eq("x")].iloc[0]
        np.testing.assert_array_equal(row[native["CPE38_KEYS_DX"]].to_numpy(float),fit.beta)
        self.assertEqual(actual.gopt,fit.gopt)

    def test_full_file_fallback_and_settings_isolation(self):
        ns=namespace(self.document)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/"27_OCO_FINAL_POINTS_sample_3.xlsx").write_bytes(b"sample must not be read")
            settings=settings_for(ns)
            settings["ridge_valves"]["RK7"]=.7
            (folder/"extension_settings.json").write_text(json.dumps(settings))
            with self.assertRaises(FileNotFoundError):
                ns["ep_locate_inputs"](dict(product="A",folder=folder))
            (folder/"27_OCO_FINAL_POINTS.parquet").write_bytes(b"broken parquet")
            fixture().to_excel(folder/"27_OCO_FINAL_POINTS.xlsx",index=False)
            data,loaded,path,_=ns["ep_read_product"](dict(product="A",folder=folder))
            self.assertEqual(len(data),len(fixture()))
            self.assertEqual(path.suffix,".xlsx")
            ns["ep_restore_settings"](loaded)
            self.assertEqual(ns["EP_RIDGE_VALVE_HYPER"]["RK7"],.7)
            loaded["ridge_valves"]["RK7"]=1.3
            self.assertEqual(ns["EP_RIDGE_VALVE_HYPER"]["RK7"],.7)
            ns["ep_restore_settings"](loaded)
            self.assertEqual(ns["EP_RIDGE_VALVE_HYPER"]["RK7"],1.3)

    def run_kernel(self,no_edge=False):
        ns=namespace(self.document)
        with tempfile.TemporaryDirectory(prefix="edge-inner-") as temp:
            folder=Path(temp)
            input_bytes={}
            for index,product in enumerate(["KGVM","KHVF","PBVC"]):
                root=folder/"edge_comparison_input"/product
                root.mkdir(parents=True)
                destination=root/"stages" if index==1 else root
                destination.mkdir(exist_ok=True)
                frame=fixture((index+1)*.001,no_edge=no_edge)
                frame.to_parquet(destination/"27_OCO_FINAL_POINTS.parquet",index=False)
                settings=settings_for(ns)
                settings["ridge_valves"]["RK7"]=[.7,1.3,2.][index]
                (root/"extension_settings.json").write_text(json.dumps(settings))
                input_bytes[destination/"27_OCO_FINAL_POINTS.parquet"]=(destination/"27_OCO_FINAL_POINTS.parquet").read_bytes()
            notebook=nbformat.read(HERE/"OCO_Edge_Inner_Comparison.ipynb",as_version=4)
            with patch.dict(os.environ,{"IPYTHONDIR":str(folder/"ipython"),"JUPYTER_RUNTIME_DIR":str(folder/"runtime")}):
                executed=NotebookClient(notebook,kernel_name="python3",timeout=240).execute(cwd=str(folder))
            output=folder/"output_edge_inner_comparison"
            reports=pd.read_excel(output/"OCO_Edge_Inner_Comparison.xlsx",sheet_name=None)
            summary=reports["Product_summary"]
            self.assertEqual(set(summary["product"]),{"KGVM","KHVF","PBVC"})
            self.assertTrue(summary.n_wafers.eq(1).all())
            if no_edge:
                self.assertTrue(summary.n_edge_total.eq(0).all())
                self.assertTrue(summary.median_wafer_edge_prediction_RMSE_nm.isna().all())
                self.assertTrue(reports["Shot_reference"].empty)
            else:
                self.assertTrue(summary.n_eligible_shots.eq(1).all(),summary.to_string())
                self.assertTrue(summary.edge_prediction_coverage.gt(0).all())
                np.testing.assert_allclose(summary.median_wafer_edge_prediction_RMSE_nm,[1.,2.,3.],rtol=0,atol=1e-7)
                diag=reports["Shot_reference"]
                self.assertTrue(diag.photo_transn_seq.astype(str).eq("9007199254741999").all())
                for index in range(3):
                    points=pd.read_parquet(output/"points"/f"Product_{index+1:02d}_edge_shots.parquet")
                    self.assertEqual(set(points["product"]),{["KGVM","KHVF","PBVC"][index]})
                    values=points.loc[points.edge_deviation_x.notna(),"edge_deviation_x"]*1000
                    self.assertAlmostEqual(np.sqrt(np.mean(values**2)),index+1,places=7)
            for path,content in input_bytes.items():
                self.assertEqual(path.read_bytes(),content)
            self.assertEqual(len(list((output/"plots").glob("*.png"))),5)
            saved=json.loads((output/"comparison_settings.json").read_text())
            self.assertEqual([source["original_settings"]["ridge_valves"]["RK7"] for source in saved["sources"]],[.7,1.3,2.])
            artifact=Path('/tmp/edge-inner-diagnostics-tests')/('no_edge' if no_edge else 'three_products')
            artifact.mkdir(parents=True,exist_ok=True)
            nbformat.write(executed,artifact/"executed.ipynb")
            for path in list(output.glob("*.xlsx"))+list((output/"plots").glob("*.png")):
                (artifact/path.name).write_bytes(path.read_bytes())

    def test_actual_kernel_three_products_and_exports(self):
        self.run_kernel()

    def test_actual_kernel_no_edge(self):
        self.run_kernel(no_edge=True)

    def test_notebook_valid_and_under_1000_lines(self):
        notebook=nbformat.read(HERE/"OCO_Edge_Inner_Comparison.ipynb",as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type=="code":
                compile(cell.source,cell.id,"exec")
                self.assertLess(len(cell.source.splitlines()),1000)
                self.assertFalse(cell.outputs)


if __name__=="__main__":
    unittest.main()
