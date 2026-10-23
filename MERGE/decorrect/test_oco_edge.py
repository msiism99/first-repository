"""Validate edge ingestion, scaling and downstream notebook execution with synthetic DB tables."""
import ast
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / "MRC_PSM_decorrect.ipynb"
PHOTO = 9007199254741003


def section(document, number):
    cells = document["cells"]
    index = next(i for i, cell in enumerate(cells) if cell["cell_type"] == "markdown" and cell["source"].startswith(f"## {number:02d}."))
    return cells[index + 1]["source"]


def definitions(source, namespace):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "functions", "exec"), namespace)


def fixtures():
    lotrows = {}
    for mode, step, transn, slots in [("adi", "VC075040", 101, [11, 12]), ("main", "VC077251", 201, [11, 12]), ("edge", "VC077252", 301, [11])]:
        rows = []
        for slot in slots:
            rows.append(dict(lot_transn_seq=transn, photo_transn_seq=PHOTO, impala_insert_time="2026-10-21 15:00", db_user="SIMAXP2",
                             timestamp="2026-10-21 12:00", lotid="LOT_A", slotid=slot, pstepseq="VC075030", mstepseq=step,
                             ppid="PPID", peqpid="EXPO", chuckid="EX1" if slot % 2 else "EX2", reticleid="RETICLE",
                             steppitch_x=20000., steppitch_y=20000., mapshift_x=0., mapshift_y=0., dmargin_x=0., dmargin_y=0.,
                             outlr_resdl_spec_ratio=3., chip_x_qty=2, chip_y_qty=2, psm_mmo_ref_eqp_id="REF", per_shot_mrc_id="BASE_20261021"))
        lotrows[mode] = pd.DataFrame(rows)
    edge = lotrows["edge"]
    lotrows["edge"] = pd.concat([edge.assign(lot_transn_seq=300, impala_insert_time="2026-10-20"), edge,
                                  edge.assign(lot_transn_seq=399, photo_transn_seq=PHOTO + 2, impala_insert_time="2026-10-22"),
                                  edge.assign(lot_transn_seq=398, slotid=9), edge.assign(lot_transn_seq=397, lotid="LOT_B")], ignore_index=True)
    main_shots = [(-2, -1), (-1, 0), (0, 0), (1, 0), (2, 1), (0, 2)]
    edge_shots = [(7, 0)]
    raw = []
    for mode, transn, slots in [("adi", 101, [11, 12]), ("main", 201, [11, 12]), ("edge", 301, [11, 9])]:
        shots = main_shots + edge_shots if mode == "adi" else edge_shots if mode == "edge" else main_shots
        tests = range(1, 5) if mode == "adi" else [1, 81, 82, 83, 84]
        for slot in slots:
            for stamp, multiplier in [("2026-10-21 10:00", 100.), ("2026-10-21 14:00" if mode == "edge" else "2026-10-21 12:00", 1.)]:
                for test in tests:
                    local = test if mode == "adi" else test - 80 if test > 80 else 0
                    rx = (3000. if mode == "edge" else -2000.) + 700. * local
                    ry = (-1) ** local * 1100.
                    common = dict(lot_transn_seq=transn, slot_id=slot, transn_occur_date=stamp, test_point_no=test, mrc_x_valn=.01, mrc_y_valn=.02)
                    raw.append(dict(common, data_kind="TESTDATA", coordinate_x=0., coordinate_y=0., value_x=rx, value_y=ry))
                    for sx, sy in shots:
                        xval, yval = multiplier * (.001 + .0001 * local + .00001 * sx), multiplier * (-.002 - .0001 * local + .00001 * sy)
                        raw.append(dict(common, data_kind="RAWDATA", coordinate_x=sx, coordinate_y=sy, value_x=xval, value_y=yval))
                        if mode == "adi":
                            raw.append(dict(common, data_kind="PERSHOT", coordinate_x=sx, coordinate_y=sy, value_x=.0001, value_y=.0002))
    raw = pd.DataFrame(raw)
    expo = pd.DataFrame([dict(apc_hist_index_no=700 + slot, apc_trocs_hist_index_no=900 + slot, impala_insert_time="2026-10-21",
                             seq_no=slot, lot_id="LOT_A", slot_id=slot, photo_step_seq="VC075030", metro_step_seq="VC077251",
                             photo_date="2026-10-20", photo_transn_seq=PHOTO, mmo_mrc_ref_eqp_id="MMO") for slot in [11, 12]])
    f1 = pd.DataFrame([dict(photo_transn_seq=PHOTO, lotid="LOT_A", slotid=slot, base_eqp_id1="BASE", impala_insert_time="2026-10-21") for slot in [11, 12]])
    mrc = f1.drop(columns="base_eqp_id1").copy()
    mrc["subname"] = "CMP"
    for key in [f"wk{i}" for i in range(1, 21)] + [f"rk{i}" for i in range(3, 21)]:
        mrc[key] = .0004 if key == "wk1" else .0006 if key == "wk2" else 0.
    history, eexy, psm, trocs = [], [], [], []
    for slot in [11, 12]:
        common = dict(lot_id="LOT_A", step_seq="VC075030", eqp_id="EXPO", sub_eqp_id="EX1" if slot % 2 else "EX2", tkin_tsdt="2026-10-20 09:00")
        history.append(dict(common, apc_hist_index_no=700 + slot, apc_group_name="PHOTO_MAIN", ppid="PPID", reticle_id="RETICLE", run_type="NORMAL", event_tsdt="2026-10-20 10:00"))
        eexy.append(dict(common, apc_trocs_hist_index_no=900 + slot, event_tsdt_eexy="2026-10-20 10:00"))
        for sx, sy in main_shots + edge_shots:
            key = dict(apc_hist_index_no=900 + slot, pos_x_valn=sx * 20., pos_y_valn=sy * 20.)
            psm.append(dict(key, **{f"mrc_k{i}_valn": .0001 if i == 1 else .0002 if i == 2 else 0. for i in range(1, 73)}))
            trocs.append(dict(key, **{f"rk{i}_valn": .00007 if i == 1 else .00008 if i == 2 else 0. for i in range(1, 73)}))
    return dict(lot_adi=lotrows["adi"], lot_main=lotrows["main"], lot_edge=lotrows["edge"], raw=raw, expo=expo, f1=f1, mrc=mrc,
                history=pd.DataFrame(history), eexy=pd.DataFrame(eexy), psm=pd.DataFrame(psm), trocs=pd.DataFrame(trocs))


MOCK_DB = '''import re
import sys
import types
query_calls = []
fixture_dir = Path.cwd() / "fixture"
def get_data(sql):
    query_calls.append(sql)
    if "apc_nautil_dat_lotinfo" in sql:
        name = "lot_edge" if "'VC077252'" in sql else "lot_main" if "'VC077251'" in sql else "lot_adi"
    elif "apc_nautil_dat_rawdata" in sql:
        frame = pd.read_parquet(fixture_dir / "raw.parquet")
        match = re.search(r"r\\.lot_transn_seq IN \\(([^)]+)\\)", sql)
        return frame[frame.lot_transn_seq.isin([int(v.strip()) for v in match.group(1).split(",")])].copy()
    elif "apc_expo_overlay_lot" in sql:
        name = "expo"
    elif "apc_nautil_paramdata" in sql:
        name = "mrc" if "'CMP'" in sql else "f1"
    elif "apc_apc_lot_hist" in sql:
        name = "eexy" if "apc_group_name = 'PHOTO_EEXY_GRP'" in sql else "history"
    elif "apc_apc_photo_shot_input_hist" in sql:
        name = "psm" if "mrc_k1_valn" in sql else "trocs"
    else:
        raise AssertionError("Unexpected SQL: " + sql)
    return pd.read_parquet(fixture_dir / (name + ".parquet"))
sys.modules["bigdataquery"] = types.SimpleNamespace(getData=get_data)
'''


class EdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(MAIN.read_text())
        cls.data = fixtures()
        cls.ns = {"np": np, "pd": pd}
        common = next(c["source"] for c in cls.doc["cells"] if c["cell_type"] == "code" and "def integer(" in c["source"])
        definitions(common, cls.ns)
        for num in [4, 5, 6]:
            definitions(section(cls.doc, num), cls.ns)
        # Cell 08 contains constants used by its functions.
        source = section(cls.doc, 8)
        tree = ast.parse(source)
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) or (isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ["RENAME", "FINAL_COLUMNS", "OCO_PROVENANCE_COLUMNS"])]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "assemble", "exec"), cls.ns)
        settings = next(c["source"] for c in cls.doc["cells"] if c["cell_type"] == "code" and "class PipelineConfig:" in c["source"])
        cfg_node = next(n for n in ast.parse(settings).body if isinstance(n, ast.ClassDef))
        cls.ns["dataclass"] = dataclass
        exec(compile(ast.Module(body=[cfg_node], type_ignores=[]), "config", "exec"), cls.ns)
        cls.cfg = cls.ns["PipelineConfig"](reference_date="2026-10-23")

    def test_selection_keeps_exact_exposure_and_missing_edge_wafer(self):
        edge, status = self.ns["select_oco_edge_history"](self.data["lot_edge"], self.data["lot_main"])
        self.assertEqual(edge.lot_transn_seq.tolist(), [301])
        self.assertEqual(edge.photo_transn_seq.tolist(), [PHOTO])
        self.assertEqual(status.slotid.tolist(), [11, 12])
        self.assertEqual(status.edge_history_found.tolist(), [True, False])
        self.assertEqual(len(self.ns["select_oco_edge_history"](pd.DataFrame(), self.data["lot_main"])[1]), 2)
        empty, diag = self.ns["select_oco_edge_history"](pd.DataFrame(), pd.DataFrame())
        self.assertTrue(empty.empty and diag.empty)
        self.ns["LOT_COLUMNS"] = "l.lotid,l.slotid,l.photo_transn_seq"
        sql = self.ns["oco_edge_lotinfo_sql"](self.cfg, self.data["lot_main"])
        self.assertIn("l.mstepseq = 'VC077252'", sql)
        self.assertIn(f"l.photo_transn_seq IN ({PHOTO})", sql)
        self.assertIn("PARTITION BY l.lotid, l.slotid, l.photo_transn_seq", sql)

    def test_scaling_only_raw_xy_and_idempotent(self):
        frame = self.data["raw"].query("lot_transn_seq == 301").copy()
        before = frame.copy(deep=True)
        prepared = self.ns["prepare_oco_raw_source"](frame, "oco_edge", "VC077252", .6)
        raw = frame.data_kind.eq("RAWDATA")
        np.testing.assert_allclose(prepared.loc[raw, ["value_x", "value_y"]], frame.loc[raw, ["value_x", "value_y"]] * .6)
        pd.testing.assert_frame_equal(prepared.loc[~raw, frame.columns], frame.loc[~raw])
        pd.testing.assert_frame_equal(prepared[["coordinate_x", "coordinate_y", "mrc_x_valn", "mrc_y_valn"]], frame[["coordinate_x", "coordinate_y", "mrc_x_valn", "mrc_y_valn"]])
        pd.testing.assert_frame_equal(frame, before)
        again = self.ns["prepare_oco_raw_source"](prepared, "oco_edge", "VC077252", .6)
        pd.testing.assert_frame_equal(again, prepared)
        changed = self.ns["prepare_oco_raw_source"](prepared, "oco_edge", "VC077252", .4)
        np.testing.assert_allclose(changed.loc[raw, "value_x"], frame.loc[raw, "value_x"] * .4)
        for bad in [np.nan, np.inf, -.1]:
            with self.assertRaises(ValueError):
                self.ns["PipelineConfig"](oco_edge_scale=bad)
        with self.assertRaises(ValueError):
            self.ns["PipelineConfig"](target_mstepseq_oco_edge="VC077251")

    def prepared_inputs(self):
        edge, status = self.ns["select_oco_edge_history"](self.data["lot_edge"], self.data["lot_main"])
        all_lots = pd.concat([self.data["lot_main"], edge], ignore_index=True)
        base = self.ns["prepare_oco_raw_source"](self.data["raw"].query("lot_transn_seq == 201"), "oco_main", "VC077251")
        extra = self.ns["prepare_oco_raw_source"](self.data["raw"].query("lot_transn_seq == 301"), "oco_edge", "VC077252", .6)
        combined = self.ns["latest_raw_batch"](pd.concat([base, extra], ignore_index=True), all_lots)
        expo = self.data["expo"].rename(columns={"lot_id": "lotid"})
        measured = self.ns["assemble_measurements"](combined, all_lots, expo, self.data["f1"], "OCO", self.cfg)
        return combined, measured, status

    def test_batch_testdata_e2_and_baseline_adi_main_invariance(self):
        combined, measured, status = self.prepared_inputs()
        self.assertEqual(set(measured.Wafer), {11, 12})
        self.assertEqual(len(measured), 52)
        self.assertTrue(measured.GROUP.eq("E2").all())
        edge = measured[measured.measurement_source.eq("oco_edge")]
        self.assertEqual(len(edge), 4)
        self.assertEqual(set(edge.coordinate_X), {3700., 4400., 5100., 5800.})
        self.assertTrue(edge.UNIQUE_ID.str.contains("_OCO_EDGE_301").all())
        np.testing.assert_allclose(edge.X_reg, edge.X_reg_original * .6)
        np.testing.assert_allclose(edge.Y_reg, edge.Y_reg_original * .6)
        coverage = self.ns["oco_edge_coverage"](measured, status)
        self.assertEqual(coverage.n_main_points.tolist(), [24, 24])
        self.assertEqual(coverage.n_edge_points.tolist(), [4, 0])
        old = json.loads(subprocess.check_output(["git", "show", "50dcf60:MERGE/MRC_PSM_decorrect.ipynb"], cwd=HERE))
        old_ns = dict(self.ns)
        old_source = section(old, 8)
        exec(old_source[:old_source.index("\ndf_adi_measured =")], old_ns)
        for mode, lots, transn in [("ADI", "lot_adi", 101), ("OCO", "lot_main", 201)]:
            raw = self.ns["latest_raw_batch"](self.data["raw"].query("lot_transn_seq == @transn"), self.data[lots])
            expo = self.data["expo"].rename(columns={"lot_id": "lotid"})
            expected = old_ns["assemble_measurements"](raw, self.data[lots], expo, self.data["f1"], mode, self.cfg)
            actual_raw = self.ns["prepare_oco_raw_source"](raw, "oco_main", "VC077251") if mode == "OCO" else raw
            actual = self.ns["assemble_measurements"](actual_raw, self.data[lots], expo, self.data["f1"], mode, self.cfg)
            pd.testing.assert_frame_equal(expected, actual[expected.columns])

    def test_only_replacement_cells_changed_and_patch_is_exact(self):
        old = json.loads(subprocess.check_output(["git", "show", "50dcf60:MERGE/MRC_PSM_decorrect.ipynb"], cwd=HERE))
        old_by_id = {c["id"]: c for c in old["cells"]}
        changed = [c["id"] for c in self.doc["cells"] if c["cell_type"] == "code" and c["source"] != old_by_id[c["id"]]["source"]]
        patch_doc = nbformat.read(HERE / "OCO_Edge_Replacement_Cells.ipynb", as_version=4)
        self.assertEqual(len(changed), 5)
        for c in patch_doc.cells:
            if c.cell_type == "code":
                self.assertIn(c.source, [s["source"] for s in self.doc["cells"] if s["cell_type"] == "code"])
        for path in [MAIN, HERE / "OCO_Edge_Replacement_Cells.ipynb"]:
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            for c in notebook.cells:
                if c.cell_type == "code":
                    compile(c.source, c.id, "exec")
                    self.assertLess(len(c.source.splitlines()), 1000)
                    self.assertFalse(c.outputs)

    def test_actual_kernel_00_through_28_and_disabled_edge(self):
        with tempfile.TemporaryDirectory(prefix="oco-edge-") as temp:
            base = Path(temp)
            (base / "fixture").mkdir()
            for name, frame in self.data.items():
                frame.to_parquet(base / "fixture" / (name + ".parquet"), index=False)
            notebook = nbformat.read(MAIN, as_version=4)
            stop = next(i for i, c in enumerate(notebook.cells) if c.cell_type == "markdown" and c.source.startswith("## 29."))
            notebook.cells = notebook.cells[:stop]
            settings = next(c for c in notebook.cells if c.cell_type == "code" and "class PipelineConfig:" in c.source)
            settings.source = settings.source.replace("cfg.reference_date = None", 'cfg.reference_date = "2026-10-23"').replace("EXCEL_PREVIEW_ROWS = 10000", "EXCEL_PREVIEW_ROWS = 500").replace("PREVIEW_ROWS = 10", "PREVIEW_ROWS = 2")
            mock_index = notebook.cells.index(settings) + 1
            notebook.cells.insert(mock_index, nbformat.v4.new_code_cell(MOCK_DB))
            notebook.cells.append(nbformat.v4.new_code_cell('''
assert len(df_final_oco) == 52 and set(df_final_oco.Wafer) == {11,12}
assert len(df_final_adi) == 56
edge = df_final_oco[df_final_oco.measurement_source.eq("oco_edge")]
assert len(edge) == 4 and edge.GROUP.eq("E2").all()
np.testing.assert_allclose(edge.X_reg, edge.X_reg_original * .6)
np.testing.assert_allclose(edge.Y_reg, edge.Y_reg_original * .6)
np.testing.assert_allclose(edge.raw_x, edge.X_reg_original * .6 + .0004 - .0001)
np.testing.assert_allclose(edge.raw_y, edge.Y_reg_original * .6 + .0006 - .0002)
assert set(df_oco_edge_coverage.n_edge_points) == {0,4}
assert set(df_oco_edge_coverage.n_main_points) == {24}
assert df_decomposition_check.passed.all()
assert df_oco_cpe.measurement_source.eq("oco_edge").sum() == 4
assert df_oco_cpe.loc[df_oco_cpe.measurement_source.eq("oco_edge"), "trocs_status"].eq("matched").all()
np.testing.assert_allclose(df_oco_cpe.loc[df_oco_cpe.measurement_source.eq("oco_edge"), "trocs_fit_x"], .00007)
assert df_final_shot_oco[["DieX","DieY"]].notna().all().all()
assert len(pd.read_excel(STAGE_DIR / "08_OCO_EDGE_COVERAGE.xlsx")) == 2
saved = pd.read_parquet(STAGE_DIR / "27_OCO_FINAL_POINTS.parquet")
assert saved.measurement_scale.eq(.6).sum() == 4
assert saved.source_lot_transn_seq.eq(301).sum() == 4
assert saved.photo_transn_seq.eq(9007199254741003).all()
assert df_rawdata_oco_edge_query.loc[df_rawdata_oco_edge_query.data_kind.eq("TESTDATA"), "value_x"].isin([3000.,3700.,4400.,5100.,5800.]).all()
main_saved = df_oco_measured[df_oco_measured.measurement_source.eq("oco_main")].reset_index(drop=True).copy()
calls_before = len(query_calls)
cfg.include_oco_edge = False
'''))
            for num in [4, 5, 6, 8]:
                notebook.cells.append(nbformat.v4.new_code_cell(section(self.doc, num)))
            notebook.cells.append(nbformat.v4.new_code_cell('''
assert not any("'VC077252'" in sql for sql in query_calls[calls_before:])
assert len(df_oco_measured) == 48 and df_oco_measured.measurement_scale.eq(1.).all()
pd.testing.assert_frame_equal(df_oco_measured.reset_index(drop=True), main_saved)
assert df_oco_edge_coverage.edge_point_status.eq("disabled").all()
print("OCO edge: full pipeline and disabled-mode checks passed")
'''))
            with patch.dict(os.environ, {"IPYTHONDIR": str(base / "ipython"), "JUPYTER_RUNTIME_DIR": str(base / "runtime")}):
                executed = NotebookClient(notebook, kernel_name="python3", timeout=240).execute(cwd=str(base))
            artifact = Path("/tmp/oco-edge-test")
            artifact.mkdir(exist_ok=True)
            nbformat.write(executed, artifact / "executed.ipynb")


if __name__ == "__main__":
    unittest.main()
