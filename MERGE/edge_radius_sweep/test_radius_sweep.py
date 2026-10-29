"""Native full-refit equivalence, held-out outer points, strict coverage and actual 20-case kernels."""
import ast
from dataclasses import dataclass
import copy
from functools import lru_cache
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

HERE=Path(__file__).resolve().parent


def code(document,number):
    return next(c["source"] for c in document["cells"] if c["cell_type"]=="code" and c["id"]==f"edge-radius-{number}")


def original_reference():
    ns=dict(np=np,pd=pd,dataclass=dataclass)
    notebook=json.loads((HERE.parent/"MRC_PSM_decorrect.ipynb").read_text())
    for number in range(22,27):
        i=next(i for i,c in enumerate(notebook["cells"]) if c["cell_type"]=="markdown" and c["source"].startswith(f"## {number}."))
        exec(notebook["cells"][i+1]["source"],ns)
    ns["RIDGE_VALVE_HYPER"]["RK7"]=.7
    ns["SPAN_TOLERANCE"]=.012
    settings=dict(kmrc_definition="OCO_E1_RAW_MINUS_ADI_RAW",use_virtual_chip_points=True,virtual_wafer_radius_um=144000.,span_tolerance=.012,
        minimum_ridge=ns["MINIMUM_RIDGE"],add_ridge=ns["ADD_RIDGE"],max_gopt_return=ns["MAX_GOPT_RETURN"],max_span_iter=ns["MAX_SPAN_ITER"],cd_tol=ns["CD_TOL"],
        ridge_valves=copy.deepcopy(ns["RIDGE_VALVE_HYPER"]),active_span_limits=copy.deepcopy(ns["RK_SPAN_LIMITS_OVO3_38P_F2F"]),
        cpe_options=dict(span_mode="OVO3_38P_F2F",min_points_guide=10,eval_grid_n=10,ridge_regression=True,gopt_spec=.95,gopt_tolerance=.001,gopt_type=1,use_span_box_constraint=True))
    return ns,settings


def fixture(native,settings,no_edge=False):
    rng=np.random.default_rng(20261029)
    frames=[]
    cases=[("A",11,0.,"center"),("A",11,138000.,"mixed_far"),("A",11,138100.,"mixed_near"),("A",12,0.,"center"),("A",12,146500.,"outer"),("B",7,0.,"center")]
    for lot,wafer,cx,kind in cases:
        if no_edge and kind!="center":
            continue
        if kind=="outer":
            rx,ry=rng.uniform(-200,200,24),rng.uniform(-200,200,24)
        else:
            rx,ry=rng.uniform(-5000,5000,40),rng.uniform(-4500,4500,40)
            if kind.startswith("mixed"):
                boundary=144000.-cx
                rx=np.r_[rx,rng.uniform(boundary+100,boundary+1600,12)]
                ry=np.r_[ry,rng.uniform(-300,300,12)]
                if kind=="mixed_far":
                    rx=np.r_[rx,rng.uniform(boundary+2100,boundary+2900,8)]
                    ry=np.r_[ry,rng.uniform(-300,300,8)]
        n=len(rx)
        radius=np.hypot(cx+rx,ry)
        outer=radius>144000.
        frame=pd.DataFrame(dict(LOT_ID=lot,Wafer=wafer,fcp_x=cx,fcp_y=0.,coordinate_X=rx,coordinate_Y=ry,radius=radius,DieX=int(cx//1000),DieY=0,
            TEST=np.arange(81,81+n),GROUP="E2",STEP_PITCH_X=20000.,STEP_PITCH_Y=20000.,CHIP_X_NUM=2,CHIP_Y_NUM=2))
        frame["photo_transn_seq"]=pd.Series([9007199254741999+wafer]*n,dtype="Int64")
        frame["measurement_source"]=np.where(outer,"oco_edge","oco_main")
        frame["source_mstepseq"]=np.where(outer,"VC077252","VC077251")
        frame["measurement_scale"]=np.where(outer,.5,1.)
        for axis,sign in [("x",1.),("y",-1.)]:
            original=sign*(.002+2e-8*rx-3e-8*ry+1e-12*rx*ry+outer*np.maximum(radius-144000.,0)*2e-7)+rng.normal(0,.00005,n)
            frame[f"{axis.upper()}_reg_original"]=original
            frame[f"raw_minus_total_fit_{axis}"]=original*frame.measurement_scale-.00035
        frames.append(frame)
    result=pd.concat(frames,ignore_index=True)
    return native["run_cpe38_vba_style_shotwise"](result,label="SAVED",**settings["cpe_options"])[0]


def namespace(document,settings):
    ns=dict(np=np,pd=pd,dataclass=dataclass,copy=copy,json=json,Path=Path,lru_cache=lru_cache)
    ns.update(EP_AXES=["x","y"],EP_STD_DDOF=1,EP_INNER_RADIUS_UM=144000.,EP_MAX_RADIUS_UM=147000.,ER_FIT_RADII_MM=[146.,147.],ER_SCALES=[i/10 for i in range(1,11)],ER_SVD_RCOND=1e-12,ER_BASELINE_ATOL_UM=1e-9)
    ns["EP_WAFER_KEYS"]=["product","LOT_ID","Wafer"]
    ns["EP_SHOT_KEYS"]=ns["EP_WAFER_KEYS"]+["fcp_x","fcp_y"]
    functions=[n for n in ast.parse(code(document,0)).body if isinstance(n,ast.FunctionDef)]
    exec(compile(ast.Module(body=functions,type_ignores=[]),"inputs","exec"),ns)
    for number in [1,2,3,4,5]:
        exec(code(document,number),ns)
    ns["options"]=ns["ep_restore_settings"](copy.deepcopy(settings))
    return ns


class RadiusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=json.loads((HERE/"OCO_Edge_Radius_Sweep.ipynb").read_text())
        cls.native,cls.settings=original_reference()
        cls.base=fixture(cls.native,cls.settings)

    def test_point_counts_same_shot_gap_and_boundaries(self):
        ns=namespace(self.document,self.settings)
        points,audit=ns["er_prepare_product"](self.base,"VM","y")
        self.assertEqual(audit["n_used"],len(self.base))
        counts=ns["er_point_counts"](points,ns["EP_WAFER_KEYS"])
        self.assertEqual(int(counts.n_total.sum()),len(points))
        self.assertEqual(int(counts.n_edge.sum()),int(points.radius.gt(144000.).sum()))
        np.testing.assert_allclose(counts.edge_point_fraction,counts.n_edge/counts.n_total)
        gaps=ns["er_mixed_input_gap"](points,ns["EP_SHOT_KEYS"],"y",points.loc[points._mixed_shot])
        self.assertEqual(len(gaps),2)
        for row in gaps.itertuples():
            shot=points.loc[points.fcp_x.eq(row.fcp_x)]
            inner=shot.loc[shot.region.eq("INNER"),"input100_y"]*1000
            edge=shot.loc[shot.region.eq("EDGE"),"input100_y"]*1000
            self.assertAlmostEqual(row.delta_M3S_edge_minus_inner_nm,abs(edge.mean())+3*edge.std(ddof=1)-abs(inner.mean())-3*inner.std(ddof=1))
        source=self.base.head(4).copy()
        source["radius"]=[144000.,146000.,147000.,147001.]
        prepared,audit=ns["er_prepare_product"](source,"VM","y")
        self.assertEqual(audit["n_outside_radius"],1)
        self.assertEqual(prepared.region.tolist(),["INNER","EDGE","EDGE"])
        context=ns["er_build_contexts"](prepared,"y",ns["options"])[0]
        self.assertEqual(int(context["masks"][146.][0].sum()),2)
        self.assertEqual(int(context["masks"][147.][0].sum()),3)

    def test_native_full_refits_equal_cached_affected_shot_predictions(self):
        ns=namespace(self.document,self.settings)
        points,_=ns["er_prepare_product"](self.base,"VM","y")
        contexts=ns["er_build_contexts"](points,"y",ns["options"])
        baseline=pd.Series(np.nan,index=points.index)
        for ctx in contexts:
            baseline.loc[ctx["indices"]]=ns["er_solve_context"](ctx,147.,None)["prediction"]
        with tempfile.TemporaryDirectory() as temp:
            ns["EP_OUTPUT_DIR"]=Path(temp)
            check=ns["er_check_baseline"](points,baseline,"y",1)
            self.assertTrue(check.passed.all())
            for radius in [146.,147.]:
                for scale in [.1,.5,1.]:
                    actual=baseline.copy()
                    for ctx in contexts:
                        if ctx["affected"]:
                            actual.loc[ctx["indices"]]=ns["er_solve_context"](ctx,radius,scale)["prediction"]
                    train=points.loc[points.radius.le(radius*1000)].copy()
                    train["raw_minus_total_fit_y"]=train.input100_y
                    outer=train.region.eq("EDGE")
                    train.loc[outer,"raw_minus_total_fit_y"]+=(scale-1.)*train.loc[outer,"Y_reg_original"]
                    _,coef,_=self.native["run_cpe38_vba_style_shotwise"](train,label="NAIVE",**self.settings["cpe_options"])
                    expected=pd.Series(np.nan,index=points.index)
                    for key,shot in points.groupby(["LOT_ID","Wafer","fcp_x","fcp_y"],observed=True):
                        selected=coef.LOT_ID.eq(key[0])&coef.Wafer.eq(key[1])&coef.fcp_x.eq(key[2])&coef.fcp_y.eq(key[3])
                        if selected.any():
                            beta=coef.loc[selected,[f"{term}_Y" for term in self.native["CPE38_KEYS_DY"]]].iloc[0].to_numpy(float)
                            expected.loc[shot.index]=self.native["cpe_38para"](shot.coordinate_X,shot.coordinate_Y)[1]@beta
                    np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-13,equal_nan=True)
                    frame=points.copy()
                    frame["_metric_residual"]=points.input100_y-actual
                    metrics,_=ns["er_scenario_metrics"](frame,radius,scale)
                    for row in metrics.loc[metrics.scope.eq("ALL_SHOTS")].itertuples():
                        selected=points.LOT_ID.eq(row.LOT_ID)&points.Wafer.eq(row.Wafer)
                        if row.region=="R_LE_144MM":
                            selected &= points.radius.le(144000.)
                        values=(points.loc[selected,"input100_y"]-expected.loc[selected])*1000
                        if values.isna().any():
                            self.assertTrue(np.isnan(row.M3S_nm))
                        else:
                            self.assertAlmostEqual(row.M3S_nm,abs(values.mean())+3*values.std(ddof=1))
        near=next(c for c in contexts if c["identity"]["fcp_x"]==138100.)
        self.assertIs(ns["er_solve_context"](near,146.,.5),ns["er_solve_context"](near,147.,.5))

    def test_strict_coverage_and_empty_training_do_not_fake_improvement(self):
        ns=namespace(self.document,self.settings)
        points,_=ns["er_prepare_product"](self.base,"VC","x")
        contexts=ns["er_build_contexts"](points,"x",ns["options"])
        prediction=pd.Series(np.nan,index=points.index)
        for ctx in contexts:
            ns["er_solve_context"](ctx,147.,None)
            solution=ns["er_solve_context"](ctx,146.,1.)
            prediction.loc[ctx["indices"]]=solution["prediction"]
            if ctx["identity"]["fcp_x"]==146500.:
                self.assertEqual(solution["diagnostic"]["status"],"no_training_points")
                self.assertTrue(np.isnan(solution["prediction"]).all())
        frame=points.copy()
        frame["_metric_residual"]=points.input100_x-prediction
        wafer,shot=ns["er_scenario_metrics"](frame,146.,1.)
        row=wafer.loc[wafer.LOT_ID.eq("A")&wafer.Wafer.eq(12)&wafer.scope.eq("ALL_SHOTS")&wafer.region.eq("ALL_R_LE_147MM")].iloc[0]
        self.assertTrue(np.isnan(row.M3S_nm))
        self.assertEqual(row.metric_status,"incomplete_prediction")
        self.assertLess(row.coverage_fraction,1.)
        inner=wafer.loc[wafer.LOT_ID.eq("A")&wafer.Wafer.eq(12)&wafer.scope.eq("ALL_SHOTS")&wafer.region.eq("R_LE_144MM")].iloc[0]
        self.assertTrue(np.isfinite(inner.M3S_nm))
        self.assertEqual(inner.coverage_fraction,1.)

    def test_reexecuting_engine_cache_and_baseline_failure(self):
        ns=namespace(self.document,self.settings)
        X=np.arange(30.).reshape(10,3)/100+np.eye(10,3)
        V=X[:5]
        ridge=np.array([.1,.2,.3])
        expected=self.native["gopt_value"](X,V,ridge,gopt_type=1)
        self.assertEqual(ns["ep_gopt_value"](X,V,ridge,gopt_type=1),expected)
        exec(code(self.document,4),ns)
        self.assertEqual(ns["ep_gopt_value"](X,V,ridge,gopt_type=1),expected)
        self.assertEqual(ns["ep_gopt_value"](X,V,ridge,gopt_type=1),expected)
        self.assertGreater(ns["er_cached_geometry_gopt"].cache_info().hits,0)
        points,_=ns["er_prepare_product"](self.base,"VM","y")
        with tempfile.TemporaryDirectory() as temp:
            ns["EP_OUTPUT_DIR"]=Path(temp)
            wrong=points.CPE_fit_y.copy()
            wrong.iloc[0]+=.001
            with self.assertRaises(ValueError):
                ns["er_check_baseline"](points,wrong,"y",1)
            self.assertTrue((Path(temp)/"Baseline_Parity_Failed_Product_01.xlsx").is_file())

    def run_kernel(self,no_edge=False):
        with tempfile.TemporaryDirectory(prefix="radius-sweep-") as temp:
            folder=Path(temp)
            originals={}
            for index,product in enumerate(["KGVM","KHVF","PBVC"]):
                root=folder/"edge_comparison_input"/product
                root.mkdir(parents=True)
                destination=root/"stages" if index==1 else root
                destination.mkdir(exist_ok=True)
                frame=fixture(self.native,self.settings,no_edge=True) if no_edge else self.base.copy()
                inactive="y" if product=="PBVC" else "x"
                frame=frame.drop(columns=[f"raw_minus_total_fit_{inactive}",f"{inactive.upper()}_reg_original"])
                path=destination/"27_OCO_FINAL_POINTS.parquet"
                frame.to_parquet(path,index=False)
                originals[path]=path.read_bytes()
                (root/"extension_settings.json").write_text(json.dumps(self.settings))
            notebook=nbformat.read(HERE/"OCO_Edge_Radius_Sweep.ipynb",as_version=4)
            setup=next(c for c in notebook.cells if c.cell_type=="code" and c.id=="edge-radius-0")
            setup.source="\n".join(f"EP_BASE_DIR = Path({str(folder)!r})" if line.startswith("EP_BASE_DIR =") else line for line in setup.source.splitlines())
            working=folder/"kernel_temp"
            working.mkdir()
            with patch.dict(os.environ,{"IPYTHONDIR":str(folder/"ipython"),"JUPYTER_RUNTIME_DIR":str(folder/"runtime")}):
                executed=NotebookClient(notebook,kernel_name="python3",timeout=240).execute(cwd=str(working))
            output=folder/"output_edge_radius_sweep"
            report=pd.read_excel(output/"OCO_Edge_Radius_Sweep.xlsx",sheet_name=None)
            self.assertTrue(report["Baseline_parity"].passed.all())
            metrics=report["Wafer_M3S"]
            self.assertEqual(set(metrics.fit_radius_mm),{146,147})
            self.assertEqual(set(metrics.scale_pct),set(range(10,101,10)))
            self.assertEqual(len(metrics),3*3*20*4)
            self.assertEqual(len(list((output/"cases").glob("*_Wafer_M3S.parquet"))),60)
            self.assertEqual(len(list((output/"plots").glob("*.png"))),10)
            for product,axis in [("KGVM","y"),("KHVF","y"),("PBVC","x")]:
                self.assertTrue(metrics.loc[metrics["product"].eq(product),"axis"].eq(axis).all())
            unchanged=metrics.loc[metrics.LOT_ID.eq("B")&metrics.scope.eq("ALL_SHOTS")]
            self.assertTrue(unchanged.groupby(["product","region"]).M3S_nm.nunique().eq(1).all())
            curves=report["Product_curves"]
            if no_edge:
                self.assertTrue(report["Shot_inner_M3S_wide"].empty)
                self.assertTrue(report["Mixed_shot_input_comparison"].empty)
                self.assertTrue(curves.loc[curves.scope.eq("ALL_SHOTS")].n_wafers_used.eq(3).all())
            else:
                inner=curves.loc[curves.scope.eq("ALL_SHOTS")&curves.region.eq("R_LE_144MM")]
                allpoints=curves.loc[curves.scope.eq("ALL_SHOTS")&curves.region.eq("ALL_R_LE_147MM")]
                self.assertTrue(inner.n_wafers_used.eq(3).all())
                self.assertTrue(allpoints.n_wafers_used.eq(2).all())
                trace=pd.read_parquet(output/"points"/"Product_03_R146_S100.parquet")
                heldout=trace.loc[trace.radius.gt(146000.)&trace.fcp_x.eq(138000.)]
                self.assertTrue((~heldout.used_for_fit).all())
                self.assertTrue(heldout.CPE_fit_x.notna().all())
                np.testing.assert_allclose(heldout.metric_residual_x,heldout.input100_x-heldout.CPE_fit_x,rtol=0,atol=1e-17)
                meta=report["Edge_shot_point_counts"]
                self.assertTrue(meta.photo_transn_seq.astype(str).str.startswith("900719925474").all())
                shot_long=pd.read_parquet(output/"tables"/"Shot_M3S.parquet")
                self.assertNotIn("Shot_M3S",report)
                self.assertEqual(len(shot_long),3*3*20*2)
            for path,content in originals.items():
                self.assertEqual(path.read_bytes(),content)
            artifact=Path("/tmp/edge-radius-sweep-tests")/("no_edge" if no_edge else "three_products")
            artifact.mkdir(parents=True,exist_ok=True)
            nbformat.write(executed,artifact/"executed.ipynb")
            for path in list(output.glob("*.xlsx"))+list((output/"plots").glob("*.png")):
                (artifact/path.name).write_bytes(path.read_bytes())

    def test_actual_kernel_twenty_cases_and_exports(self):
        self.run_kernel()

    def test_actual_kernel_no_edge(self):
        self.run_kernel(no_edge=True)

    def test_valid_notebook_and_cells_under_1000_lines(self):
        notebook=nbformat.read(HERE/"OCO_Edge_Radius_Sweep.ipynb",as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type=="code":
                compile(cell.source,cell.id,"exec")
                self.assertLess(len(cell.source.splitlines()),1000)
                self.assertFalse(cell.outputs)


if __name__=="__main__":
    unittest.main()
