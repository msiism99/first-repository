"""Numerical and real-kernel validation with synthetic stages; no production data required."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'ADI_OCO_Correlation.ipynb'


def load_reference():
    spec = importlib.util.spec_from_file_location('original_cpe_for_correlation_test', ROOT / '013.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    tree = ast.parse((ROOT / '012.py').read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'osr_wk20p_rk20p')
    scope = {'np': np}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '012.py', 'exec'), scope)
    return module, scope['osr_wk20p_rk20p']


def make_stages(folder, n_wafers=8):
    reference, basis = load_reference()
    rng = np.random.default_rng(20261016)
    folder.mkdir(parents=True, exist_ok=True)
    frames, expected_betas = {}, []
    cpe_names = {'x': reference.CPE38_KEYS_DX, 'y': reference.CPE38_KEYS_DY}
    global_names = {'x': [f'WK{i}' for i in range(1, 21, 2)] + [f'RK{i}' for i in range(3, 21, 2)], 'y': [f'WK{i}' for i in range(2, 21, 2)] + [f'RK{i}' for i in range(4, 21, 2)]}
    pitch_x, pitch_y = 26000., 33000.
    shots = [(x, y) for x in range(4) for y in range(4 - x)] + [(0, 4)]
    rx_adi, ry_adi = rng.uniform(-12000, 12000, 32), rng.uniform(-15000, 15000, 32)
    rx_oco, ry_oco = rng.uniform(-11000, 11500, 29), rng.uniform(-15500, 14000, 29)
    points_by_mode = {'ADI': [], 'OCO': []}
    raw_wk, raw_rk, raw_cpe, old_mrc, old_psm, residuals = [], [], [], [], [], {'ADI': [], 'OCO': []}
    scales = np.array([.02, .3, .2, 1., 1., 1., .05, .05, .05, .05, .5, .4, .03, .03, .03, .01, .01, .01, .01])
    intercepts = {axis: rng.normal(0, 0.2, 19) * scales for axis in ['x', 'y']}
    slopes = {axis: rng.uniform(.01, .05, 19) * scales for axis in ['x', 'y']}
    for wafer in range(n_wafers):
        lot, slot, photo = f'LOT_TEST_{wafer // 2}', 9 + wafer % 2, 1000 + wafer
        identity = dict(LOT_ID=lot, Wafer=slot, photo_transn_seq=photo)
        beta_adi = {axis: intercepts[axis] + wafer * slopes[axis] for axis in ['x', 'y']}
        for mode in ['ADI', 'OCO']:
            local_x, local_y = (rx_adi, ry_adi) if mode == 'ADI' else (rx_oco, ry_oco)
            centers = shots if mode == 'ADI' else [(-x, -y) for x, y in shots]
            records = []
            for shot, (sx, sy) in enumerate(centers):
                for point, (rx, ry) in enumerate(zip(local_x, local_y)):
                    records.append(dict(identity, fcp_x=sx * pitch_x, fcp_y=sy * pitch_y, coordinate_X=rx, coordinate_Y=ry, GROUP='E1' if mode == 'ADI' else 'E2', TEST=point + (1 if mode == 'ADI' else 81), UNIQUE_ID2=f'{photo}-{mode}-{shot}-{point}', STEP_PITCH_X=pitch_x, STEP_PITCH_Y=pitch_y, CHIP_X_NUM=3, CHIP_Y_NUM=3))
            frame = pd.DataFrame(records)
            matrices = basis(*(frame[col].to_numpy(float) for col in ['fcp_x', 'fcp_y', 'coordinate_X', 'coordinate_Y']))
            assert all(np.linalg.matrix_rank(matrix) == 19 for matrix in matrices)
            expected = {}
            for axis, matrix in zip(['x', 'y'], matrices):
                beta = beta_adi[axis] if mode == 'ADI' else 1.25 * beta_adi[axis] + 0.015 * scales
                expected[axis] = beta
                noise = rng.normal(0, (.0003 + wafer * .00003) * (1 if mode == 'ADI' else 1.3), len(frame))
                noise -= matrix @ np.linalg.lstsq(matrix, noise, rcond=None)[0]
                frame['X_reg' if axis == 'x' else 'Y_reg'] = matrix @ beta + noise
                for term, value in zip(global_names[axis], beta):
                    expected_betas.append(dict(identity, mode=mode, axis=axis, term=term, k_expected=value))
            old_m_values = {axis: beta_adi[axis] * .4 + rng.normal(0, .01, 19) * scales for axis in ['x', 'y']}
            for axis, matrix in zip(['x', 'y'], matrices):
                frame[f'mrc_fit_{axis}'] = -matrix @ old_m_values[axis] if mode == 'ADI' else 0.
                frame['PSM_X' if axis == 'x' else 'PSM_Y'] = 0.
                frame[f'psm_fit_{axis}'] = 0.
            if mode == 'ADI':
                applied_row = dict(lotid=lot, slotid=slot, photo_transn_seq=photo, impala_insert_time='2026-10-16', subname='CMP')
                for axis in ['x', 'y']:
                    applied_row.update({name.lower(): value for name, value in zip(global_names[axis], old_m_values[axis])})
                old_mrc.append(applied_row)
                for (cx, cy), group in frame.groupby(['fcp_x', 'fcp_y']):
                    applied = dict(lot_id=lot, sub_eqp_id='EX1' if slot % 2 else 'EX2', pos_x_valn=cx, pos_y_valn=cy, event_tsdt='2026-10-16 09:00', tkin_tsdt='2026-10-16 08:00', apc_hist_index_no=photo + 10000)
                    applied.update({f'mrc_k{i}_valn': 0. for i in range(1, 73)})
                    for axis, matrix in zip(['x', 'y'], reference.cpe_38para(group['coordinate_X'], group['coordinate_Y'])):
                        beta = rng.normal(0, .001, len(cpe_names[axis]))
                        if wafer == 0 and axis == 'x':
                            beta[cpe_names[axis].index('RK7')] = 0.
                        for name, value in zip(cpe_names[axis], beta):
                            applied[f'mrc_k{int(name[2:])}_valn'] = value
                        k_fit = matrix @ beta
                        frame.loc[group.index, f'psm_fit_{axis}'] = k_fit
                        frame.loc[group.index, 'PSM_X' if axis == 'x' else 'PSM_Y'] = k_fit + (.00002 if axis == 'x' else -.00003) * (wafer + 1)
                    if wafer == 0:
                        applied['mrc_k7_valn'] = np.nan  # active partial NaN is evaluated as zero
                        applied['mrc_k21_valn'] = 1234.  # outside the supported CPE38: never use in delta
                    old_psm.append(applied)
            for axis in ['x', 'y']:
                frame[f'raw_{axis}'] = frame['X_reg' if axis == 'x' else 'Y_reg'] - frame[f'mrc_fit_{axis}'] - frame['PSM_X' if axis == 'x' else 'PSM_Y']
            wk_row, rk_row = dict(identity), dict(identity)
            for axis, matrix in zip(['x', 'y'], matrices):
                raw_beta = np.linalg.lstsq(matrix, frame[f'raw_{axis}'], rcond=None)[0]
                frame[f'raw_minus_total_fit_{axis}'] = frame[f'raw_{axis}'] - matrix @ raw_beta
                for term, value in zip(global_names[axis], raw_beta):
                    (wk_row if term.startswith('WK') else rk_row)[f'{term}_{axis.upper()}'] = value
            with redirect_stdout(io.StringIO()):
                final, coefficients, summary = reference.run_cpe38_vba_style_shotwise(frame, label=mode, gopt_type=1)
            points_by_mode[mode].append(frame)
            residuals[mode].append(final)
            if mode == 'ADI':
                raw_wk.append(wk_row)
                raw_rk.append(rk_row)
                raw_cpe.append(coefficients)
    frames['15_ADI_FINAL'] = pd.concat(points_by_mode['ADI'], ignore_index=True)
    frames['15_OCO_FINAL'] = pd.concat(points_by_mode['OCO'], ignore_index=True)
    frames['27_ADI_FINAL_POINTS'] = pd.concat(residuals['ADI'], ignore_index=True)
    frames['27_OCO_FINAL_POINTS'] = pd.concat(residuals['OCO'], ignore_index=True)
    frames['09_MRC_ADI_INPUT'] = pd.DataFrame(old_mrc)
    frames['12_PSM_INPUT'] = pd.DataFrame(old_psm)
    frames['21_ADI_WK_WAFER_COEFFICIENTS'] = pd.DataFrame(raw_wk)
    frames['21_ADI_RK_WAFER_COEFFICIENTS'] = pd.DataFrame(raw_rk)
    frames['27_ADI_CPE_SHOT_COEFFICIENTS'] = pd.concat(raw_cpe, ignore_index=True)
    # Existing raw coefficient files omit photo IDs; exercise exposure-key restoration.
    for name in ['21_ADI_WK_WAFER_COEFFICIENTS', '21_ADI_RK_WAFER_COEFFICIENTS']:
        frames[name] = frames[name].drop(columns='photo_transn_seq')
    for name, frame in frames.items():
        frame.to_parquet(folder / f'{name}.parquet', index=False)
    return frames, pd.DataFrame(expected_betas)


def functions_from_notebook(base):
    env = dict(np=np, pd=pd, Path=Path, Sequence=list, Tuple=tuple, UM_TO_NM=1000., STD_DDOF=1, PAIR_KEYS=['LOT_ID', 'Wafer', 'photo_transn_seq'], COORD_COLS=['fcp_x', 'fcp_y', 'coordinate_X', 'coordinate_Y'], WK_RK_MIN_POINTS=19, K_REFERENCE='ADI', MIN_CORR_WAFERS=3, CORR_MIN_RANGE_NM=1e-6)
    from scipy.stats import pearsonr, spearmanr
    env.update(pearsonr=pearsonr, spearmanr=spearmanr)
    for cell in nbformat.read(NOTEBOOK, as_version=4).cells:
        if cell.cell_type != 'code':
            continue
        if 'models' in cell.metadata.get('tags', []):
            exec(compile(cell.source, 'models', 'exec'), env)
        else:
            nodes = [node for node in ast.parse(cell.source).body if isinstance(node, ast.FunctionDef)]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), 'definitions', 'exec'), env)
    return env


class CorrelationTests(unittest.TestCase):
    def test_notebook_structure_and_legacy_basis(self):
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        nbformat.validate(notebook)
        self.assertTrue(all(c.execution_count is None and not c.outputs for c in notebook.cells if c.cell_type == 'code'))
        code = '\n'.join(c.source for c in notebook.cells if c.cell_type == 'code')
        self.assertNotIn('from MERGE', code)
        self.assertNotIn('bigdataquery', code)
        self.assertLess(sum(len(c.source.splitlines()) for c in notebook.cells if c.cell_type == 'code'), 1000)
        env = functions_from_notebook(None)
        original, basis = load_reference()
        rng = np.random.default_rng(7)
        x, y, rx, ry = rng.normal(size=(4, 50)) * 10000
        for actual, expected in zip(env['osr_wk20p_rk20p'](x, y, rx, ry), basis(x, y, rx, ry)):
            np.testing.assert_array_equal(actual, expected)
        for actual, expected in zip(env['cpe_38para'](rx, ry), original.cpe_38para(rx, ry)):
            np.testing.assert_array_equal(actual, expected)

    def test_small_constant_and_invalid_inputs(self):
        env = functions_from_notebook(None)
        self.assertEqual(env['correlation_result'](pd.DataFrame({'x': [1., 2.], 'y': [2., 3.]}), 'x', 'y')['status'], 'too_few_wafers')
        self.assertEqual(env['correlation_result'](pd.DataFrame({'x': [1e-13, 2e-13, 3e-13], 'y': [1., 2., 3.]}), 'x', 'y')['status'], 'constant_or_nearly_constant')
        with self.assertRaisesRegex(ValueError, 'key 중복'):
            env['row_dict_lookup'](pd.DataFrame({'LOT_ID': ['A', 'A'], 'Wafer': [1, 1]}), ['LOT_ID', 'Wafer'], 'test')
        points = pd.DataFrame({'LOT_ID': ['A', 'A'], 'Wafer': [1, 1], 'photo_transn_seq': [1, 2]})
        with self.assertRaisesRegex(ValueError, '여러 photo'):
            env['add_photo_keys'](pd.DataFrame({'LOT_ID': ['A'], 'Wafer': [1]}), points, 'coeff')
        frame = pd.DataFrame({'LOT_ID': ['A'], 'Wafer': [1], 'photo_transn_seq': [1], 'fcp_x': [0.], 'fcp_y': [0.], 'coordinate_X': [1.], 'coordinate_Y': [1.], 'X_reg': [1.], 'Y_reg': [2.]})
        fitted, coeff, diag = env['fit_reg_terms'](frame, 'ADI')
        self.assertTrue(coeff.empty)
        self.assertEqual(diag['status'].iloc[0], 'skip_too_few_points')
        self.assertTrue(fitted['reg_total_fit_x_um'].isna().all())
        degenerate = pd.concat([frame] * 30, ignore_index=True)
        fitted, coeff, diag = env['fit_reg_terms'](degenerate, 'ADI')
        self.assertEqual(diag['status'].iloc[0], 'rank_deficient')
        self.assertFalse(coeff['fit_valid'].any())
        with tempfile.TemporaryDirectory() as temp:
            env.update(STAGE_DIR=Path(temp), INPUT_STEMS={'TEST': 'sample'}, input_manifest=[])
            pd.DataFrame({'value': [1, 2]}).to_excel(Path(temp) / 'sample_sample_2.xlsx', index=False)
            with self.assertRaisesRegex(FileNotFoundError, 'sample'):
                env['load_input']('TEST')
            pd.DataFrame({'value': [1, 2, 3]}).to_excel(Path(temp) / 'sample.xlsx', index=False)
            self.assertEqual(len(env['load_input']('TEST')), 3)

    def test_actual_kernel_simulation_statistics_coefficients_and_exports(self):
        with tempfile.TemporaryDirectory(prefix='adi-oco-correlation-') as temp:
            base = Path(temp)
            frames, expected_betas = make_stages(base / 'output_decorrect_notebook/stages')
            notebook = nbformat.read(NOTEBOOK, as_version=4)
            for cell in notebook.cells:
                if 'settings' in cell.metadata.get('tags', []):
                    tree = ast.parse(cell.source)
                    node = next(n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'BASE_DIR')
                    lines = cell.source.splitlines()
                    lines[node.lineno - 1] = f'BASE_DIR = Path({str(base)!r})'
                    cell.source = '\n'.join(lines).replace('PLOT_DPI = 170', 'PLOT_DPI = 75')
            notebook.cells.append(nbformat.v4.new_code_cell('''
saved_lookup = psm_old_lookup
missing_key = psm_old_lookup.index[0]
psm_old_lookup = psm_old_lookup.drop(index=missing_key)
missing_sim, _, _, _ = simulate_adi(df_adi)
mask = psm_key(df_adi, from_points=True).eq(missing_key)
assert missing_sim.loc[mask, "sim_reg_x_um"].isna().all()
assert missing_sim.loc[mask, "simulation_psm_status"].eq("missing_or_invalid_applied_k").all()
assert missing_sim.loc[~mask, "simulation_valid"].all()
psm_old_lookup = saved_lookup
print("Missing PSM key correctly produces NaN and leaves other shots valid")
'''))
            runtime = {'IPYTHONDIR': str(base / 'ipython'), 'JUPYTER_RUNTIME_DIR': str(base / 'jupyter-runtime')}
            with patch.dict(os.environ, runtime):
                executed = NotebookClient(notebook, kernel_name='python3', timeout=180).execute(cwd=str(base))
            artifact = Path(os.environ.get('CORRELATION_TEST_ARTIFACTS', '/tmp/adi-oco-correlation-test'))
            artifact.mkdir(parents=True, exist_ok=True)
            nbformat.write(executed, artifact / 'executed.ipynb')
            output = base / 'output_adi_oco_correlation'
            tables = output / 'tables'
            statistics = pd.read_parquet(tables / '04_REG_WAFER_STATISTICS.parquet')
            for mode in ['ADI', 'OCO']:
                expected_stats = frames[f'15_{mode}_FINAL'].groupby(['LOT_ID', 'Wafer', 'photo_transn_seq'])[['X_reg', 'Y_reg']].agg(['mean', 'std'])
                indexed = statistics.set_index(['LOT_ID', 'Wafer', 'photo_transn_seq'])
                for axis, column in [('x', 'X_reg'), ('y', 'Y_reg')]:
                    np.testing.assert_allclose(indexed[f'{mode.lower()}_reg_{axis}_mean_nm'], expected_stats[(column, 'mean')] * 1000, rtol=1e-12)
                    np.testing.assert_allclose(indexed[f'{mode.lower()}_reg_{axis}_3sigma_nm'], expected_stats[(column, 'std')] * 3000, rtol=1e-12)
            sim = pd.read_parquet(tables / '08_ADI_SIMULATED_POINTS.parquet')
            self.assertEqual(len(sim), len(frames['15_ADI_FINAL']))
            self.assertTrue(sim['simulation_valid'].all())
            for axis, reg in [('x', 'X_reg'), ('y', 'Y_reg')]:
                forward = sim[reg] - sim[f'mrc_applied_{axis}_um'] - sim[f'psm_applied_{axis}_um'] + sim[f'mrc_ideal_{axis}_um'] + sim[f'psm_ideal_{axis}_um']
                np.testing.assert_allclose(sim[f'sim_reg_{axis}_um'], forward, rtol=1e-10, atol=1e-13)
                np.testing.assert_allclose(sim[f'delta_mrc_{axis}_um'], sim[f'mrc_applied_{axis}_um'] - sim[f'mrc_ideal_{axis}_um'], atol=1e-13)
                np.testing.assert_allclose(sim[f'delta_psm_{axis}_um'], sim[f'psm_applied_{axis}_um'] - sim[f'psm_ideal_{axis}_um'], atol=1e-13)
            difference = pd.read_parquet(tables / '08_SIMULATION_VS_SAVED_ADI_RESIDUAL.parquet')
            self.assertGreater(difference['simulation_minus_saved_residual_x_nm'].abs().max(), .1)
            # The simulation must retain the measured PERSHOT-vs-K discrepancy, not shortcut to residual.
            bias = sim['PSM_X'] - sim['psm_applied_x_um']
            np.testing.assert_allclose(difference['simulation_minus_saved_residual_x_nm'], bias * 1000, atol=1e-10)
            mrc_delta = pd.read_parquet(tables / '08_MRC_APPLIED_IDEAL_DELTA_K.parquet')
            psm_delta = pd.read_parquet(tables / '08_PSM38_APPLIED_IDEAL_DELTA_K.parquet')
            np.testing.assert_allclose(mrc_delta['delta_k'], mrc_delta['k_applied'] - mrc_delta['k_ideal'])
            np.testing.assert_allclose(psm_delta['delta_k'], psm_delta['k_applied'] - psm_delta['k_ideal'])
            self.assertEqual(psm_delta.groupby(['LOT_ID', 'Wafer', 'fcp_x', 'fcp_y']).size().unique().tolist(), [38])
            self.assertTrue(psm_delta['applied_k_was_nan'].any())
            self.assertTrue(psm_delta['nonzero_outside_cpe38'].gt(0).any())
            for mode in ['ADI', 'OCO']:
                actual = pd.read_parquet(tables / f'10_{mode}_REG_WK_RK_COEFFICIENTS.parquet')
                expected = expected_betas.loc[expected_betas['mode'].eq(mode)]
                merged = actual.merge(expected, on=['LOT_ID', 'Wafer', 'photo_transn_seq', 'mode', 'axis', 'term'], validate='1:1')
                self.assertEqual(len(actual), len(expected))
                np.testing.assert_allclose(merged['k_reg'], merged['k_expected'], rtol=1e-7, atol=1e-10)
            nm = pd.read_parquet(tables / '11_REG_K_NM_LONG.parquet')
            original, basis = load_reference()
            for key, reference in frames['15_ADI_FINAL'].groupby(['LOT_ID', 'Wafer', 'photo_transn_seq']):
                matrices = basis(*(reference[col] for col in ['fcp_x', 'fcp_y', 'coordinate_X', 'coordinate_Y']))
                for axis, matrix in zip(['x', 'y'], matrices):
                    names = [f'WK{i}' for i in range(1 if axis == 'x' else 2, 21, 2)] + [f'RK{i}' for i in range(3 if axis == 'x' else 4, 21, 2)]
                    selected = nm.loc[nm['LOT_ID'].eq(key[0]) & nm['Wafer'].eq(key[1]) & nm['axis'].eq(axis)]
                    for row in selected.itertuples():
                        contribution = matrix[:, names.index(row.term)] * row.k_reg * 1000
                        self.assertAlmostEqual(row.max_nm, np.max(contribution), places=9)
                        self.assertAlmostEqual(row.peak_abs_nm, np.max(np.abs(contribution)), places=9)
                        self.assertAlmostEqual(row.signed_peak_nm, np.sign(row.k_reg) * row.peak_abs_nm, places=9)
            correlation = pd.read_parquet(tables / '12_REG_K_CORRELATIONS.parquet')
            self.assertTrue(correlation['n_wafer'].eq(8).all())
            np.testing.assert_allclose(correlation['pearson_r'], 1., atol=1e-8)
            manifest = pd.read_csv(output / 'saved_files.csv')
            for row in manifest.itertuples():
                path = Path(row.parquet)
                self.assertTrue(path.is_file())
                self.assertEqual(len(pd.read_parquet(path)), row.rows)
            self.assertEqual(len(list((output / 'plots').glob('*.png'))), 7)
            images = [output for cell in executed.cells if cell.cell_type == 'code' for output in cell.outputs if 'image/png' in output.get('data', {})]
            self.assertGreaterEqual(len(images), 7)
            for path in (output / 'plots').glob('*.png'):
                with Image.open(path) as image:
                    self.assertGreater(image.width, 500)
                if path.name in ['04_REG_vs_REG.png', '12_REG_K_WK_01.png']:
                    (artifact / path.name).write_bytes(path.read_bytes())
            settings = json.loads((output / 'run_settings.json').read_text())
            self.assertEqual(settings['psm_inactive_delta_k'], 0)
            self.assertFalse(settings['point_matching'])
            self.assertIsNone(settings['group_filter'])
            self.assertEqual(settings['k_reference'], 'ADI')


if __name__ == '__main__':
    unittest.main()
