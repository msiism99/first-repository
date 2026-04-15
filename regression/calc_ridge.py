# calc_ridge.py
# Ridge Regression functions for CPE analysis
# 프로젝트9: Ridge Regression 기능 구현

import numpy as np
import logging
from ridge_config import get_ridge_valve
from config import (
    RIDGE_G_OPT_SPEC,
    RIDGE_G_OPT_TOLERANCE,
    RIDGE_G_OPT_MAX_ITER,
    RIDGE_SPAN_TOLERANCE,
    RIDGE_SPAN_MAX_ITER,
    RIDGE_MIN_LAMBDA,
    RIDGE_MAX_LAMBDA,
    RIDGE_LAMBDA_INCREMENT
)


def calculate_gopt(X, XTX_inv, eval_points=None):
    """
    Calculate G-optimality (G-opt) value

    G-opt is the maximum prediction variance across evaluation points.
    Formula: G-opt = sqrt(max(diag(H)))
    where H = X_eval * (X'X)^-1 * X_eval'

    Args:
        X: Design matrix (n_points x n_params)
        XTX_inv: Inverse of (X'X + λI) matrix
        eval_points: Evaluation design matrix (optional, uses X if None)

    Returns:
        float: G-optimality value
    """
    if eval_points is None:
        eval_points = X

    # Hat matrix: H = X_eval * (X'X)^-1 * X_eval'
    # For efficiency, compute diagonal only: diag(H) = sum(X_eval * (X'X)^-1 * X_eval', axis=1)
    # Or: diag(H) = sum((X_eval @ XTX_inv) * X_eval, axis=1)

    H_diag = np.sum((eval_points @ XTX_inv) * eval_points, axis=1)

    # G-opt = sqrt(max(diag(H)))
    max_h = np.max(H_diag)

    # Handle edge cases
    if max_h < 0:
        logging.warning(f"⚠️  Negative Hat matrix diagonal: {max_h}. Returning 999.")
        return 999.0
    elif max_h >= 100:
        logging.warning(f"⚠️  Very large Hat matrix diagonal: {max_h}. G-opt may be unreliable.")
        return np.sqrt(max_h)
    else:
        # 이정진님 로직: sqrt를 적용
        return np.sqrt(max_h)


def apply_ridge_to_matrix(XTX, lambda_values, param_indices):
    """
    Apply Ridge penalty to normal equation matrix (X'X)

    Ridge regression: (X'X + λI)^-1 X'y
    where λ is applied to diagonal elements

    Args:
        XTX: X'X matrix (n_params x n_params)
        lambda_values: Dictionary {param_index: lambda_value}
        param_indices: List of parameter indices in order

    Returns:
        np.ndarray: (X'X + λI) matrix
    """
    XTX_ridge = XTX.copy()

    # Add lambda to diagonal elements
    for i, param_idx in enumerate(param_indices):
        if param_idx in lambda_values:
            XTX_ridge[i, i] += lambda_values[param_idx]

    return XTX_ridge


def ridge_up_gopt_fast(
    current_gopt,
    start_ridge,
    end_ridge,
    start_gopt,
    end_gopt,
    target_gopt=RIDGE_G_OPT_SPEC
):
    """
    Fast Ridge lambda adjustment using Newton-like method

    VBA reference: ridge_up_Gopt_fast (z3_Fall_back_Ridge_up.txt line 1232-1344)

    Formula: next_ridge = end_ridge - end_gopt / slope_gopt
    where slope_gopt = (end_gopt - start_gopt) / (end_ridge - start_ridge)

    Args:
        current_gopt: Current G-opt value
        start_ridge: Lower bound of ridge multiplier
        end_ridge: Upper bound of ridge multiplier
        start_gopt: G-opt at start_ridge
        end_gopt: G-opt at end_ridge
        target_gopt: Target G-opt value (default: 1.0)

    Returns:
        float: Next ridge multiplier to try
    """
    # Calculate slope
    if abs(end_ridge - start_ridge) < 1e-10:
        # Ridge values too close, use increment
        return end_ridge + RIDGE_LAMBDA_INCREMENT

    slope_gopt = (end_gopt - start_gopt) / (end_ridge - start_ridge)

    # Newton method: next = end - (end_gopt - target) / slope
    # Simplified: next = end - end_gopt / slope (when target ≈ 1)
    if abs(slope_gopt) < 1e-10:
        # Slope too small, use increment
        return end_ridge + RIDGE_LAMBDA_INCREMENT

    next_ridge = end_ridge - (end_gopt - target_gopt) / slope_gopt

    # Clamp to valid range
    next_ridge = np.clip(next_ridge, RIDGE_MIN_LAMBDA, RIDGE_MAX_LAMBDA)

    return next_ridge


def ridge_up_gopt_slow(
    start_ridge,
    end_ridge,
    target_gopt=RIDGE_G_OPT_SPEC
):
    """
    Slow Ridge lambda adjustment using binary search

    VBA reference: ridge_up_Gopt_slow (z3_Fall_back_Ridge_up.txt line 1408-1447)

    Formula: next_ridge = start_ridge + (end_ridge - start_ridge) / 2

    Args:
        start_ridge: Lower bound of ridge multiplier
        end_ridge: Upper bound of ridge multiplier
        target_gopt: Target G-opt value (not used in binary search, kept for consistency)

    Returns:
        float: Next ridge multiplier to try (midpoint)
    """
    next_ridge = start_ridge + (end_ridge - start_ridge) / 2.0

    # Clamp to valid range
    next_ridge = np.clip(next_ridge, RIDGE_MIN_LAMBDA, RIDGE_MAX_LAMBDA)

    return next_ridge


def find_ridge_lambda_for_gopt(
    X,
    y,
    XTX,
    XTy,
    cpe_option,
    param_names,
    X_gopt_meas=None,
    X_gopt_eval=None,
    target_gopt=RIDGE_G_OPT_SPEC,
    tolerance=RIDGE_G_OPT_TOLERANCE,
    max_iter=RIDGE_G_OPT_MAX_ITER
):
    """
    Find Ridge lambda multiplier that achieves target G-optimality

    Iteratively adjusts lambda using fast (Newton) and slow (binary search) methods
    until G-opt < target_gopt or max iterations reached.

    VBA reference: ridge_initial_parameter (z3_Fall_back_Ridge_up.txt line 1470-2100)

    Args:
        X: Design matrix for regression (n_points x n_params), μm/1e6 scale
        y: Target values (n_points,)
        XTX: X'X matrix (n_params x n_params), from regression X
        XTy: X'y vector (n_params,), from regression X
        cpe_option: CPE regression option ('6para', '15para', '18para', '72para')
        param_names: List of RK parameter names in order (e.g., ['RK3', 'RK4', ...])
        X_gopt_meas: Design matrix for G-opt measurement points (mm scale)
        X_gopt_eval: Design matrix for G-opt evaluation points (mm scale)
        target_gopt: Target G-optimality value (default: 1.0)
        tolerance: Tolerance for convergence (default: 0.05)
        max_iter: Maximum iterations (default: 50)

    Returns:
        dict: {
            'lambda_multiplier': float,  # Final lambda multiplier
            'gopt': float,               # Final G-opt value
            'converged': bool,           # Whether converged
            'iterations': int,           # Number of iterations
            'history': list              # Iteration history
        }
    """
    # Backward compatibility: if not provided, use regression X
    if X_gopt_meas is None:
        X_gopt_meas = X
    if X_gopt_eval is None:
        X_gopt_eval = X

    # Get ridge valve for this CPE option
    ridge_valve = get_ridge_valve(cpe_option)

    # ✅ Build G-opt information matrix (from Fallback-style mm scale measurements)
    XTX_gopt = X_gopt_meas.T @ X_gopt_meas

    # Initialize
    lambda_mult = 0.0  # Start with no ridge penalty
    use_fast_method = True
    start_ridge = 0.0
    end_ridge = RIDGE_LAMBDA_INCREMENT
    start_gopt = None
    end_gopt = None

    # ✅ Iteration history 기록 (CSV 저장용)
    iteration_history = []

    # Check initial G-opt with no ridge penalty (lambda=0)
    try:
        # ✅ Use G-opt information matrix (not regression XTX!)
        XTX_gopt_inv_initial = np.linalg.inv(XTX_gopt)
        gopt_initial = calculate_gopt(X_gopt_meas, XTX_gopt_inv_initial, X_gopt_eval)

        # Early exit: G-opt already satisfies target
        if gopt_initial < target_gopt:
            # ✅ History 기록
            iteration_history.append({
                'iteration': 0,
                'lambda_mult': 0.0,
                'gopt': gopt_initial,
                'method': 'initial',
                'converged': True
            })
            return {
                'lambda_multiplier': 0.0,
                'gopt': gopt_initial,
                'converged': True,
                'iterations': 0,
                'history': iteration_history  # ✅ 추가
            }
    except np.linalg.LinAlgError:
        # Matrix singular without ridge, need to proceed with ridge
        pass

    for iteration in range(max_iter):
        # Build lambda dictionary
        lambda_dict = {}
        for param_name in param_names:
            lambda_dict[param_name] = lambda_mult * ridge_valve.get(param_name, 0.0)

        # ✅ Apply ridge to G-opt information matrix (not regression XTX!)
        XTX_gopt_ridge = XTX_gopt.copy()
        for i, param_name in enumerate(param_names):
            XTX_gopt_ridge[i, i] += lambda_dict[param_name]

        # Compute (X_gopt'X_gopt + λI)^-1
        try:
            XTX_gopt_inv = np.linalg.inv(XTX_gopt_ridge)
        except np.linalg.LinAlgError:
            logging.warning(f"⚠️  Matrix inversion failed at lambda={lambda_mult:.6f}. Increasing lambda.")
            lambda_mult = end_ridge
            end_ridge *= 2
            continue

        # ✅ Calculate G-opt using Fallback-style design matrices
        gopt = calculate_gopt(X_gopt_meas, XTX_gopt_inv, X_gopt_eval)

        # ✅ Iteration history 기록
        iteration_history.append({
            'iteration': iteration + 1,
            'lambda_mult': lambda_mult,
            'gopt': gopt,
            'method': 'fast' if use_fast_method else 'slow',
            'converged': False
        })

        # Log iteration progress (every 5 iterations or at convergence)
        if iteration % 5 == 0 or iteration == max_iter - 1:
            logging.info(
                f"    Ridge iter {iteration+1}/{max_iter}: lambda={lambda_mult:.6e}, "
                f"G-opt={gopt:.4f}, target={target_gopt:.2f}±{tolerance:.2f}, "
                f"method={'fast' if use_fast_method else 'slow'}"
            )

        # Check convergence
        if gopt < target_gopt and gopt >= (target_gopt - tolerance):
            # ✅ 마지막 기록 업데이트
            iteration_history[-1]['converged'] = True
            # Success: within tolerance
            return {
                'lambda_multiplier': lambda_mult,
                'gopt': gopt,
                'converged': True,
                'iterations': iteration + 1,
                'history': iteration_history  # ✅ 추가
            }

        # Update bounds and choose next lambda
        if use_fast_method:
            # Fast method (Newton-like)
            if gopt >= target_gopt:
                # Need to increase lambda
                if start_gopt is None:
                    start_gopt = gopt
                    start_ridge = lambda_mult
                    end_ridge = lambda_mult + RIDGE_LAMBDA_INCREMENT
                    lambda_mult = end_ridge
                else:
                    # Have both bounds, use Newton method
                    end_gopt = gopt
                    end_ridge = lambda_mult
                    lambda_mult = ridge_up_gopt_fast(
                        gopt, start_ridge, end_ridge, start_gopt, end_gopt, target_gopt
                    )
            else:
                # G-opt below target, switch to slow method for fine-tuning
                end_gopt = gopt
                end_ridge = lambda_mult
                use_fast_method = False
                lambda_mult = ridge_up_gopt_slow(start_ridge, end_ridge, target_gopt)
        else:
            # Slow method (binary search)
            if gopt >= target_gopt:
                # G-opt still too high, increase lower bound
                start_ridge = lambda_mult
                start_gopt = gopt
            else:
                # G-opt too low, decrease upper bound
                end_ridge = lambda_mult
                end_gopt = gopt

            # Check for convergence (ridge value precision)
            ridge_int = int(lambda_mult * 1000)
            ridge_float = lambda_mult * 1000
            if abs(ridge_int - ridge_float) < 1e-6 and ridge_int != 0:
                # Ridge value converged to 3 decimal places
                if abs(gopt - target_gopt) < tolerance * 2:
                    return {
                        'lambda_multiplier': lambda_mult,
                        'gopt': gopt,
                        'converged': True,
                        'iterations': iteration + 1
                    }

            # Next midpoint
            lambda_mult = ridge_up_gopt_slow(start_ridge, end_ridge, target_gopt)

    # Max iterations reached
    logging.warning(
        f"⚠️  Ridge G-opt adjustment did not converge after {max_iter} iterations. "
        f"Final G-opt: {gopt:.4f}, Target: {target_gopt:.4f}"
    )

    return {
        'lambda_multiplier': lambda_mult,
        'gopt': gopt,
        'converged': False,
        'iterations': max_iter,
        'history': iteration_history  # ✅ 추가
    }


def apply_ridge_lambda_to_params(lambda_mult, cpe_option, param_names):
    """
    Convert lambda multiplier to individual RK parameter lambdas

    Formula: lambda(RK_i) = lambda_multiplier * ridge_valve(RK_i)

    Args:
        lambda_mult: Ridge lambda multiplier
        cpe_option: CPE regression option
        param_names: List of RK parameter names

    Returns:
        dict: {param_name: lambda_value}
    """
    ridge_valve = get_ridge_valve(cpe_option)

    lambda_dict = {}
    for param_name in param_names:
        lambda_dict[param_name] = lambda_mult * ridge_valve.get(param_name, 0.0)

    return lambda_dict


# ============================================================================
# Ridge CPE Regression Main Function
# ============================================================================

def ridge_cpe_regression(
    X,
    y,
    cpe_option,
    param_names,
    X_gopt_meas=None,
    X_gopt_eval=None,
    eval_points=None,  # Deprecated: use X_gopt_eval instead
    initial_lambda_mult=0.0,
    enable_gopt_control=True,
    enable_span_control=False,
    span_limits=None
):
    """
    Perform CPE regression with Ridge regularization

    This function implements Ridge regression with:
    1. G-optimality control (to prevent overfitting)
    2. Span limit control (to meet hardware constraints)

    VBA reference: CPE_make_table in z1_CPE.txt

    Args:
        X: Design matrix for regression (n_points x n_params), μm/1e6 scale
        y: Target values (n_points,)
        cpe_option: CPE regression option ('6para', '15para', '18para', '72para')
        param_names: List of RK parameter names in order
        X_gopt_meas: Design matrix for G-opt measurement points (mm scale, Fallback style)
        X_gopt_eval: Design matrix for G-opt evaluation points (mm scale, Fallback style)
        eval_points: [DEPRECATED] Use X_gopt_eval instead
        initial_lambda_mult: Initial lambda multiplier (default: 0.0)
        enable_gopt_control: Enable G-opt control (default: True)
        enable_span_control: Enable span control (default: False)
        span_limits: Dictionary {param_name: limit_value} for span control

    Returns:
        dict: {
            'coefficients': np.ndarray,       # Regression coefficients
            'lambda_multiplier': float,       # Final lambda multiplier
            'lambda_dict': dict,              # Individual lambda values per RK
            'gopt': float,                    # Final G-optimality value
            'predictions': np.ndarray,        # Predicted values
            'residuals': np.ndarray,          # Residuals
            'span_violations': list,          # List of RK names exceeding span
            'converged': bool,                # Whether optimization converged
            'iterations': int                 # Total iterations
        }
    """
    # Backward compatibility: if X_gopt_eval not provided, use eval_points
    if X_gopt_eval is None and eval_points is not None:
        X_gopt_eval = eval_points
    # If X_gopt_meas not provided, use X (old behavior)
    if X_gopt_meas is None:
        X_gopt_meas = X

    # Build normal equation matrices (for regression)
    XTX = X.T @ X
    XTy = X.T @ y

    lambda_mult = initial_lambda_mult

    # Step 1: G-optimality control
    gopt_history = []  # ✅ History 저장용
    if enable_gopt_control:
        logging.info("  Ridge: Adjusting lambda for G-optimality control...")
        result = find_ridge_lambda_for_gopt(
            X, y, XTX, XTy, cpe_option, param_names,
            X_gopt_meas, X_gopt_eval  # ← NEW: Pass G-opt design matrices
        )
        lambda_mult = result['lambda_multiplier']
        gopt = result['gopt']
        converged = result['converged']
        iterations = result['iterations']
        gopt_history = result.get('history', [])  # ✅ History 가져오기

        logging.info(f"  Ridge: G-opt control completed. λ={lambda_mult:.6f}, G-opt={gopt:.4f}")
    else:
        gopt = None
        converged = True
        iterations = 0

    # Build lambda dictionary
    lambda_dict = apply_ridge_lambda_to_params(lambda_mult, cpe_option, param_names)

    # Apply Ridge to normal equations
    XTX_ridge = XTX.copy()
    for i, param_name in enumerate(param_names):
        XTX_ridge[i, i] += lambda_dict[param_name]

    # Solve: coefficients = (X'X + λI)^-1 X'y
    try:
        coefficients = np.linalg.solve(XTX_ridge, XTy)
    except np.linalg.LinAlgError:
        logging.error("❌ Ridge regression failed: Matrix is singular even with Ridge penalty.")
        raise

    # Calculate predictions and residuals
    predictions = X @ coefficients
    residuals = y - predictions

    # Step 2: Span control (to be implemented if needed)
    span_violations = []
    if enable_span_control and span_limits is not None:
        # TODO: Implement span control (balloon pushing)
        # This will be implemented in the next phase
        pass

    return {
        'coefficients': coefficients,
        'lambda_multiplier': lambda_mult,
        'lambda_dict': lambda_dict,
        'gopt': gopt,
        'predictions': predictions,
        'residuals': residuals,
        'span_violations': span_violations,
        'converged': converged,
        'iterations': iterations,
        'history': gopt_history  # ✅ History 추가
    }


# ============================================================================
# Span Control Functions (Balloon Pushing)
# ============================================================================

def check_span_violations(coefficients, param_names, span_limits):
    """
    Check which RK parameters exceed span limits

    Args:
        coefficients: Regression coefficients array
        param_names: List of RK parameter names
        span_limits: Dictionary {param_name: {'min': ..., 'max': ...}}

    Returns:
        list: List of (param_name, value, limit_type, delta) tuples for violations
              delta = how much the value exceeds the limit (nm units)
    """
    violations = []

    for i, param_name in enumerate(param_names):
        if param_name not in span_limits:
            continue

        coeff_value = coefficients[i]
        limits = span_limits[param_name]
        min_limit = limits['min']
        max_limit = limits['max']

        # Check violations
        if coeff_value > max_limit:
            delta = coeff_value - max_limit
            violations.append((param_name, coeff_value, 'max', delta))
        elif coeff_value < min_limit:
            delta = min_limit - coeff_value
            violations.append((param_name, coeff_value, 'min', delta))

    return violations


def adjust_lambda_for_span_violation(
    param_name,
    current_lambda,
    delta,
    span_limit,
    cpe_option,
    tolerance=RIDGE_SPAN_TOLERANCE
):
    """
    Increase lambda for a specific RK parameter to bring it within span

    Uses iterative adjustment similar to G-opt control

    Args:
        param_name: RK parameter name (e.g., 'RK7')
        current_lambda: Current lambda value for this RK
        delta: How much the value exceeds span limit (positive)
        span_limit: The span limit value
        cpe_option: CPE regression option
        tolerance: Convergence tolerance (nm)

    Returns:
        float: Increased lambda value
    """
    ridge_valve = get_ridge_valve(cpe_option)
    base_valve = ridge_valve.get(param_name, 0.0)

    if base_valve == 0.0:
        logging.warning(f"⚠️  {param_name} has no ridge valve. Cannot adjust lambda.")
        return current_lambda

    # Increase lambda by an increment proportional to the violation
    # Simple heuristic: lambda += delta * factor
    lambda_increment = delta * 0.1  # Tunable factor

    new_lambda = current_lambda + lambda_increment

    # Clamp to valid range
    new_lambda = np.clip(new_lambda, RIDGE_MIN_LAMBDA, RIDGE_MAX_LAMBDA)

    return new_lambda


def ridge_cpe_regression_with_span_control(
    X,
    y,
    cpe_option,
    param_names,
    span_limits,
    X_gopt_meas=None,
    X_gopt_eval=None,
    eval_points=None,  # Deprecated
    initial_lambda_mult=0.0,
    enable_gopt_control=True,
    max_span_iter=RIDGE_SPAN_MAX_ITER
):
    """
    Perform CPE regression with Ridge G-opt control AND Span control

    Implements "Balloon Pushing":
    - First, use Ridge to achieve G-opt < 1
    - Then, iteratively increase lambda for RKs exceeding span limits
    - Redistribution: Increasing lambda on one RK forces model to use other RKs

    VBA reference: z1_CPE.txt lines 2957-3600 (span_over logic)

    Args:
        X: Design matrix for regression (n_points x n_params), μm/1e6 scale
        y: Target values (n_points,)
        cpe_option: CPE regression option
        param_names: List of RK parameter names
        span_limits: Dictionary {param_name: {'min': ..., 'max': ...}}
        X_gopt_meas: Design matrix for G-opt measurement points (mm scale)
        X_gopt_eval: Design matrix for G-opt evaluation points (mm scale)
        eval_points: [DEPRECATED] Use X_gopt_eval instead
        initial_lambda_mult: Initial lambda multiplier
        enable_gopt_control: Enable G-opt control first
        max_span_iter: Maximum span control iterations

    Returns:
        dict: Same as ridge_cpe_regression, plus:
              'span_violations': Final violations
              'span_iterations': Span control iterations
    """
    # Backward compatibility
    if X_gopt_eval is None and eval_points is not None:
        X_gopt_eval = eval_points
    if X_gopt_meas is None:
        X_gopt_meas = X

    # Build normal equation matrices (for regression)
    XTX = X.T @ X
    XTy = X.T @ y

    # Step 1: G-optimality control (if enabled)
    gopt_history = []  # ✅ History 저장용
    if enable_gopt_control:
        logging.info("  Ridge: G-opt control...")
        gopt_result = find_ridge_lambda_for_gopt(
            X, y, XTX, XTy, cpe_option, param_names,
            X_gopt_meas, X_gopt_eval  # ← NEW: Pass G-opt design matrices
        )
        lambda_mult = gopt_result['lambda_multiplier']
        gopt = gopt_result['gopt']
        gopt_converged = gopt_result['converged']
        gopt_iterations = gopt_result['iterations']
        gopt_history = gopt_result.get('history', [])  # ✅ History 가져오기
        logging.info(f"  Ridge: G-opt={gopt:.4f}, λ={lambda_mult:.6f}")
    else:
        lambda_mult = initial_lambda_mult
        gopt = None
        gopt_converged = True
        gopt_iterations = 0

    # Initialize per-RK lambda dictionary
    ridge_valve = get_ridge_valve(cpe_option)
    lambda_dict = {}
    for param_name in param_names:
        lambda_dict[param_name] = lambda_mult * ridge_valve.get(param_name, 0.0)

    # Step 2: Span control iteration
    span_iterations = 0
    span_violations = []
    span_history = []  # ✅ Span control 상세 이력 저장용

    for span_iter in range(max_span_iter):
        # Apply Ridge to normal equations
        XTX_ridge = XTX.copy()
        for i, param_name in enumerate(param_names):
            XTX_ridge[i, i] += lambda_dict[param_name]

        # Solve regression
        try:
            coefficients = np.linalg.solve(XTX_ridge, XTy)
        except np.linalg.LinAlgError:
            logging.error("❌ Ridge regression failed during span control.")
            break

        # Check span violations
        violations = check_span_violations(coefficients, param_names, span_limits)

        # ✅ 현재 iteration 정보 기록
        iter_record = {
            'iteration': span_iter,
            'n_violations': len(violations),
            'coefficients': {param_names[i]: coefficients[i] for i in range(len(param_names))},
            'lambda_dict': lambda_dict.copy(),
            'violations': []
        }

        if len(violations) == 0:
            # Success: no violations
            logging.info(f"  Ridge: Span control converged after {span_iter} iterations.")
            iter_record['converged'] = True
            span_history.append(iter_record)
            span_violations = []
            span_iterations = span_iter
            break

        iter_record['converged'] = False

        # Log violations
        if span_iter == 0:
            logging.info(f"  Ridge: Span violations detected: {len(violations)} RKs")

        # Increase lambda for violating RKs (balloon pushing)
        for param_name, value, limit_type, delta in violations:
            limit = span_limits[param_name]['max'] if limit_type == 'max' else span_limits[param_name]['min']

            # Increase lambda for this RK
            current_lambda = lambda_dict[param_name]
            new_lambda = adjust_lambda_for_span_violation(
                param_name, current_lambda, delta, limit, cpe_option
            )

            lambda_dict[param_name] = new_lambda

            # ✅ Violation 상세 정보 기록
            iter_record['violations'].append({
                'param_name': param_name,
                'value': value,
                'limit': limit,
                'limit_type': limit_type,
                'delta': delta,
                'lambda_before': current_lambda,
                'lambda_after': new_lambda,
                'lambda_increase': new_lambda - current_lambda
            })

            if span_iter == 0:
                logging.info(
                    f"    {param_name}: {value:.4f} > {limit:.4f} (Δ={delta:.4f}), "
                    f"λ: {current_lambda:.6f} → {new_lambda:.6f}"
                )

        span_iterations = span_iter + 1

        # ✅ Iteration 종료, history에 추가
        span_history.append(iter_record)

    else:
        # Max iterations reached
        logging.warning(
            f"⚠️  Span control did not converge after {max_span_iter} iterations. "
            f"Remaining violations: {len(violations)}"
        )
        span_violations = violations
        span_iterations = max_span_iter

    # Final regression with converged lambdas
    XTX_ridge = XTX.copy()
    for i, param_name in enumerate(param_names):
        XTX_ridge[i, i] += lambda_dict[param_name]

    try:
        coefficients = np.linalg.solve(XTX_ridge, XTy)
    except np.linalg.LinAlgError:
        logging.error("❌ Final Ridge regression failed.")
        raise

    # Calculate predictions and residuals
    predictions = X @ coefficients
    residuals = y - predictions

    # ✅ Recalculate G-opt with final lambdas using Fallback-style design matrices
    if X_gopt_eval is not None:
        try:
            # Build G-opt information matrix with final lambdas
            XTX_gopt = X_gopt_meas.T @ X_gopt_meas
            XTX_gopt_ridge = XTX_gopt.copy()
            for i, param_name in enumerate(param_names):
                XTX_gopt_ridge[i, i] += lambda_dict[param_name]

            XTX_gopt_inv = np.linalg.inv(XTX_gopt_ridge)
            final_gopt = calculate_gopt(X_gopt_meas, XTX_gopt_inv, X_gopt_eval)
        except:
            final_gopt = gopt
    else:
        final_gopt = gopt

    return {
        'coefficients': coefficients,
        'lambda_multiplier': lambda_mult,  # Initial G-opt lambda
        'lambda_dict': lambda_dict,        # Final per-RK lambdas (after span control)
        'gopt': final_gopt,
        'predictions': predictions,
        'residuals': residuals,
        'span_violations': span_violations,
        'converged': (gopt_converged and len(span_violations) == 0),
        'iterations': gopt_iterations,
        'span_iterations': span_iterations,
        'history': gopt_history,  # G-opt control history
        'span_history': span_history  # ✅ Span control history 추가
    }
