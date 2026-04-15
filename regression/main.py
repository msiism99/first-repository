import pandas as pd
from datetime import datetime
import os
import logging
import sys


# 로깅 설정 (UTF-8 인코딩으로 이모지 지원)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_log.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Windows 콘솔 UTF-8 인코딩 설정 (cp949 이모지 문제 해결)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python 3.6 이하 버전 호환성
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Process mode 설정 반영을 위한 import 추가
# logging 설정 추가
from config import PROCESS_MODE
process_mode = PROCESS_MODE  # 또는 env/GUI 값으로 대체
logging.info(f"Process mode for regression: {process_mode}")


# design_matrix_config 에 설정된 기본 옵션들을 import
from config import DEFAULT_OSR_OPTION, DEFAULT_CPE_OPTION, DEFAULT_CPE_FIT_OPTION, DEFAULT_WK_OPTION, PROCESS_MODE
from config import FOLDER_PATH, RADIUS_THRESHOLD, MAX_INDEX, OUTLIER_THRESHOLD, DMARGIN_X, DMARGIN_Y, OUTLIER_SPEC_RATIO
from config import ENABLE_CPE_GOPT, G_OPT_THRESHOLD  # 🆕 프로젝트4: CPE G-opt 설정
from config import ENABLE_SPAN_CHECK  # 🆕 프로젝트5: Span 체크 (모니터링)
from config import ENABLE_RIDGE_REGRESSION, RIDGE_G_OPT_SPEC, ENABLE_RIDGE_SPAN_CONTROL  # 🆕 프로젝트9: Ridge


from nau_processor import (
    remove_duplicate_files,
    process_nau_file,
    save_combined_data
)


from calc_regression import (
    kmrc_decorrect,
    wk_rk_input_decorrect,
    remove_psm_add_pointmrc,
    # multi_lot_regression_and_fitting,
    detect_outliers_studentized_residual,  # outlier 판정용 추가
    reorder_coefficients,
    psm_decorrect,
    # resi_to_cpe,
    # cpe_k_to_fit,
    # ideal_psm,
    # delta_psm,
    # 🆕 WK Only 함수들 (새로 추가된 함수들)
    # wk_only_regression_and_fitting,
    robust_osr_regression_two_step,
    cpe_regression_with_gopt,  # 🆕 프로젝트4: CPE G-opt 회귀분석
    cpe_regression_with_gopt_depsm,  # 🆕 프로젝트6: PSM제거된 Residual로 CPE G-opt 회귀분석
    save_results_with_span_check,  # 🆕 프로젝트5: Span 체크 함수
    fit_cpe_k_to_measurements,  # 🆕 프로젝트7: CPE K Fitting
    fit_cpe_k_to_measurements_depsm,  # 🆕 프로젝트7: IDEAL PSM용 CPE K Fitting
    delta_psm,  # Delta PSM 계산
    cpe_regression_with_ridge,  # 🆕 프로젝트9: Ridge Regression
    cpe_regression_with_ridge_or_gopt,  # 🆕 프로젝트9: Ridge or G-opt 선택 회귀분석
    cpe_regression_with_ridge_depsm,  # 🆕 프로젝트9: Ridge Regression (DEPSM)
    cpe_regression_with_ridge_or_gopt_depsm  # 🆕 프로젝트9: Ridge or G-opt 선택 회귀분석 (DEPSM)

)

from raduis_filter import filter_by_radius  
from all_marks import extract_and_save_marks_by_unique_id




def main():
    """
    메인 분석 워크플로우:
    1. NAU 파일 처리
    2. Radius 필터링
    3. OSR(WK+RK) 회귀분석
    4. WK Only 회귀분석 (🆕)
    5. PSM, CPE 분석
    6. Zernike 분석

    """

    # ========================================
    # 분석 설정 확인 및 사용자 동의
    # ========================================
    print("\n" + "="*70)
    print(" NAU PROCESSOR - 반도체 오버레이 계측 분석 파이프라인")
    print("="*70)
    print(f"\n📊 분석 시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n[현재 설정]")
    print(f"  ├─ Process Mode      : {PROCESS_MODE}")
    print(f"  ├─ OSR Option        : {DEFAULT_OSR_OPTION}")

    # CPE 모드 명확히 표시
    if ENABLE_RIDGE_REGRESSION:
        cpe_mode_str = "Ridge (G-opt control, 차수 고정)"
        if ENABLE_RIDGE_SPAN_CONTROL:
            cpe_mode_str += " + Span control"
    elif ENABLE_CPE_GOPT:
        cpe_mode_str = "G-opt Fallback (차수 감소 18→15→6)"
    else:
        cpe_mode_str = "차수 고정 (Fallback 없음)"

    print(f"  ├─ CPE Option        : {DEFAULT_CPE_OPTION}")
    print(f"  ├─ CPE 모드          : {cpe_mode_str}")
    if ENABLE_RIDGE_REGRESSION:
        print(f"  │   └─ G-opt 목표     : < {RIDGE_G_OPT_SPEC}")
        if ENABLE_RIDGE_SPAN_CONTROL:
            from span_config import SPAN_MODE
            print(f"  │   └─ Span 모드      : {SPAN_MODE}")

    # ✅ CPE Option과 SPAN_MODE 호환성 체크 (프로젝트9)
    if ENABLE_RIDGE_REGRESSION or ENABLE_RIDGE_SPAN_CONTROL:
        from span_config import SPAN_MODE, validate_cpe_span_compatibility
        validation_result = validate_cpe_span_compatibility(
            cpe_option=DEFAULT_CPE_OPTION,
            span_mode=SPAN_MODE,
            enable_span_control=ENABLE_RIDGE_SPAN_CONTROL
        )
        if not validation_result['compatible']:
            print(f"\n{'='*70}")
            print(f"⚠️  설정 호환성 경고")
            print(f"{'='*70}")
            print(f"{validation_result['message']}")
            if validation_result['recommendation']:
                print(f"\n{validation_result['recommendation']}")
            print(f"{'='*70}\n")

    print(f"  ├─ Radius Threshold  : {RADIUS_THRESHOLD} μm")
    print(f"  └─ Outlier Threshold : {OUTLIER_THRESHOLD}")
    print("\n" + "="*70)

    # 사용자 확인
    while True:
        user_input = input("\n위 설정으로 분석을 진행하시겠습니까? (Y/N): ").strip().upper()

        if user_input == 'Y':
            print("✅ 분석을 시작합니다...\n")
            break
        elif user_input == 'N':
            print("\n❌ 분석을 중단합니다.")
            print("📝 설정을 변경하려면 config.py 파일을 수정하세요.")
            print("   - PROCESS_MODE: 'ADI' 또는 'OCO'")
            print("   - DEFAULT_OSR_OPTION: '6para', '15para', '18para', '19para', '20para'")
            print("   - RADIUS_THRESHOLD: 웨이퍼 반경 임계값 (μm)")
            print("   - OUTLIER_THRESHOLD: Outlier 판정 임계값")
            return  # 프로그램 종료
        else:
            print("⚠️  잘못된 입력입니다. Y 또는 N을 입력해주세요.")

    # config.py에 정의된 폴더 경로 사용
    folder_path = FOLDER_PATH
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 작업 시작")

    # 결과 저장 폴더 생성 (없으면 생성)
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    remove_duplicate_files(folder_path)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 중복 파일 제거 완료")



    ############################### 1. nau_processor ########################################

    rawdata_list = []
    trocs_input_list = []
    psm_input_list = []
    mrc_list = []
    wk_rk_input_list = []
    test_coord_list = []

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 시작")
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.nau'):
            file_path = os.path.join(folder_path, file_name)
            try:
                rawdata_df, trocs_input_df, psm_input_df, mrc_df, wk_rk_input_df, test_coord_df = process_nau_file(file_path)
                rawdata_list.append(rawdata_df)
                trocs_input_list.append(trocs_input_df)
                psm_input_list.append(psm_input_df)
                mrc_list.append(mrc_df)
                wk_rk_input_list.append(wk_rk_input_df)
                test_coord_list.append(test_coord_df)
                print(f"{file_name} 처리 완료")
            except Exception as e:
                print(f"{file_name} 처리 중 에러 발생: {e}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 시작")
    save_combined_data(rawdata_list, trocs_input_list, psm_input_list, mrc_list, wk_rk_input_list, test_coord_list)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 완료")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 작업 완료")

    

    

    # ----------------------------- 1.5 all_marks 마크 추출 ----------------------------- #
    from all_marks import extract_and_save_marks_by_unique_id

    # all_marks 실행 (Test_Coord.csv는 nau_processor에서 이미 저장됨)
    test_coord_path = os.path.join(results_dir, "Test_Coord.csv")
    output_marks_path = os.path.join(results_dir, "all_marks_total.csv")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 전체 마크 추출 시작.")
    extract_and_save_marks_by_unique_id(test_coord_path, output_marks_path)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 전체 마크 추출 완료.")

  
    

    ############################### 2. raduis_filter ######################################## 
    # config에 정의된 RADIUS_THRESHOLD 사용
    # RawData 파일 필터링 (results 폴더 내 파일 사용)
    input_path = os.path.join(results_dir, "RawData-1.csv")
    filtered_data_path = os.path.join(results_dir, "Radius_Filtered_RawData-1.csv")
    radius_threshold = RADIUS_THRESHOLD  # 원하는 radius 임계값 설정.  config.py에서 가져온 값
    
    print("Starting radius filtering...")
    filter_by_radius(input_path, filtered_data_path, radius_threshold)

    ############################### 2.5 data load 및 mrc decorrect ########################################

    # 데이터 로드 (results 폴더 내 파일)
    df_rawdata = pd.read_csv(filtered_data_path)
    df_mrc_input = pd.read_csv(os.path.join(results_dir, "MRC.csv"))
    df_wk_rk_input = pd.read_csv(os.path.join(results_dir, "WK_RK_INPUT.csv"))

    # MRC Decorrect
    df_mrc_de = kmrc_decorrect(df_rawdata, df_mrc_input)
    df_rawdata = pd.concat([df_rawdata, df_mrc_de], axis=1)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'MRC Decorrect 완료.')

    # WK, RK Input Decorrect
    df_mrcwkrk_de = wk_rk_input_decorrect(df_rawdata, df_wk_rk_input)
    df_rawdata = pd.concat([df_rawdata, df_mrcwkrk_de], axis=1)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'WK RK Input Decorrect 완료.')

    # Raw calculation
    df_rawdata = remove_psm_add_pointmrc(df_rawdata)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Raw 처리 완료.')

    ############################### 3. Robust OSR Regression ########################################

    # Step 1: Outlier Detection (using configured process mode with 6-parameter regression)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Outlier 판정 시작")
    df_rawdata = detect_outliers_studentized_residual(
        df_rawdata,
        threshold=OUTLIER_THRESHOLD,
        group_col='UNIQUE_ID',
        dmargin_x=DMARGIN_X,
        dmargin_y=DMARGIN_Y,
        outlier_spec_ratio=OUTLIER_SPEC_RATIO,
        process_mode=PROCESS_MODE  # 🆕 설정된 process mode 사용
    )
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Outlier 판정 완료")

    # Step 2: Robust OSR Regression (excluding outliers, using 20-parameter model)
    # Step 3: Calculate predictions for all data points (including outliers)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Robust OSR 회귀분석 시작")
    df_coeff_robust, df_rawdata = robust_osr_regression_two_step(
        df_rawdata,
        osr_option=DEFAULT_OSR_OPTION,
        process_mode=PROCESS_MODE
    )
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Robust OSR 회귀분석 완료")

    # Save robust coefficients
    df_coeff_robust = reorder_coefficients(df_coeff_robust)
    df_coeff_robust.to_csv(os.path.join(results_dir, 'OSR_K_ExceptOutlier.csv'), index=False)

    # Copy robust results to main columns for downstream analysis compatibility
    df_rawdata['residual_x'] = df_rawdata['residual_x_robust'].copy()
    df_rawdata['residual_y'] = df_rawdata['residual_y_robust'].copy()
    df_rawdata['pred_x'] = df_rawdata['pred_x_robust'].copy()
    df_rawdata['pred_y'] = df_rawdata['pred_y_robust'].copy()

    # Save final coefficients for downstream analysis
    df_coeff = df_coeff_robust
    df_coeff.to_csv(os.path.join(results_dir, 'OSR_K.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} OSR Robust Regression 완료")
    


    ############################### 3.1 PSM Decorrect ########################################
     # PSM Decorrect (psm 옵션 적용)
    df_psm_input = pd.read_csv(os.path.join(results_dir, 'PerShotMRC.csv'))
    df_psm_de = psm_decorrect(df_rawdata, df_psm_input, cpe_fit_option=DEFAULT_CPE_FIT_OPTION)
    df_rawdata = pd.concat([df_rawdata, df_psm_de], axis=1)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'PSM Decorrect 완료.')

    df_rawdata.to_csv(os.path.join(results_dir, 'RawData_with_OSR.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} OSR 완료된 RawData 저장 완료")
    





    ############################### Step 4: CPE Regression with Ridge or G-opt (프로젝트4 + 프로젝트9) ########################################

    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} " + "="*70)
    print("Step 4: CPE (Correction Per Expose) 회귀분석")
    print("="*70)

    if ENABLE_RIDGE_REGRESSION:
        print("▶ 모드: Ridge Regression")
        print(f"  ├─ 차수: {DEFAULT_CPE_OPTION} 고정 (Fallback 없음)")
        print(f"  ├─ G-opt control: ON (lambda 조정으로 G-opt < {G_OPT_THRESHOLD})")
        print(f"  └─ Span control: {'ON (풍선 누르기)' if ENABLE_RIDGE_SPAN_CONTROL else 'OFF'}")
    else:
        print(f"▶ 모드: G-opt Fallback ({'ON' if ENABLE_CPE_GOPT else 'OFF'})")
        print(f"  ├─ 기본 차수: {DEFAULT_CPE_OPTION}")
        if ENABLE_CPE_GOPT:
            print(f"  ├─ Fallback: ON (18→15→6 차수 감소)")
        else:
            print(f"  ├─ Fallback: OFF (차수 고정)")
        print(f"  └─ G-opt 임계값: {G_OPT_THRESHOLD}")

    df_cpe_k = cpe_regression_with_ridge_or_gopt(
        df_rawdata,
        default_cpe_option=DEFAULT_CPE_OPTION,
        enable_ridge=None,  # None이면 config.ENABLE_RIDGE_REGRESSION 사용
        enable_gopt=ENABLE_CPE_GOPT,
        exclude_outliers=True,
        process_mode=PROCESS_MODE,
        enable_span_check=ENABLE_RIDGE_SPAN_CONTROL  # Ridge 모드: Span control, Fallback 모드: 무시됨
    )
    df_cpe_k.to_csv(os.path.join(results_dir, 'CPE_K.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE_K.csv 저장")

 
    # ==================================================================================
    # 🆕 프로젝트5: Span 체크 (모니터링 전용)
    # ==================================================================================
    print("="*70)
    print(f"Span Check: {'활성화' if ENABLE_SPAN_CHECK else '비활성화'}")

    df_cpe_k = save_results_with_span_check(df_cpe_k, results_dir, ENABLE_SPAN_CHECK)
    # ==================================================================================
    # G-opt 관련 추가 정보 저장 (Ridge 또는 Fallback 모드)
    if ENABLE_RIDGE_REGRESSION or ENABLE_CPE_GOPT:
        # Ridge 모드와 Fallback 모드에서 다른 컬럼 사용
        if ENABLE_RIDGE_REGRESSION:
            # Ridge 모드 컬럼
            gopt_cols = ['cpe_option_used', 'gopt_x', 'gopt_y',
                         'lambda_mult_x', 'lambda_mult_y',
                         'converged_x', 'converged_y',
                         'iterations_x', 'iterations_y',
                         'n_points_total', 'n_points_used', 'n_outliers_excluded']
        else:
            # Fallback 모드 컬럼
            gopt_cols = ['cpe_option_used', 'gopt_x', 'gopt_y', 'fallback_count', 'status',
                         'n_points_total', 'n_points_used', 'n_outliers_excluded']

        # 실제 존재하는 컬럼만 선택
        id_cols = [c for c in ['UNIQUE_ID', 'UNIQUE_ID4', 'DieX', 'DieY'] if c in df_cpe_k.columns]
        existing_gopt_cols = [c for c in gopt_cols if c in df_cpe_k.columns]

        if existing_gopt_cols:
            df_cpe_k[id_cols + existing_gopt_cols].to_csv(os.path.join(results_dir, 'CPE_G-OPT.csv'), index=False)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE_G-OPT.csv 저장")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE 회귀분석 완료\n")


    ############################### Step 5: CPE K Fitting (프로젝트7) ########################################

    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} " + "="*70)
    print("Step 5: CPE K Fitting (보정 효과 확인)")
    print("="*70)
    print(f"Fitting 옵션: {DEFAULT_CPE_FIT_OPTION}")
    print("CPE K 계수를 측정 포인트에 fitting하여 보정 예측값 계산")

    df_cpe_fit = fit_cpe_k_to_measurements(
        df_rawdata,
        df_cpe_k,
        cpe_fit_option=DEFAULT_CPE_FIT_OPTION
    )

    # CPE_Fit.csv 별도 저장
    df_cpe_fit.to_csv(os.path.join(results_dir, 'CPE_Fit.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE_Fit.csv 저장")

    # df_rawdata에 컬럼 추가
    df_rawdata = pd.concat([df_rawdata, df_cpe_fit], axis=1)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} df_rawdata에 CPE fitting 컬럼 추가 완료")

    # RawData_with_CPE.csv 저장
    df_rawdata.to_csv(os.path.join(results_dir, 'RawData_with_CPE.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} RawData_with_CPE.csv 저장 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE Fitting 완료\n")




    ############################### Step 6: OCO기준 IDEAL PSM계산용. PSM제거된 Residual로 CPE ########################################

    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} " + "="*70)
    print("Step 6: PSM제거된 Residual로 CPE 회귀분석")
    print("="*70)
    if ENABLE_RIDGE_REGRESSION:
        print(f"🚀 Ridge Regression 모드 (DEPSM)")
        print(f"   CPE 옵션: {DEFAULT_CPE_OPTION} (고정, Fallback 없음)")
        print(f"   G-opt control: 자동 ON (lambda 조정)")
        print(f"   Span control: {'ON' if ENABLE_RIDGE_SPAN_CONTROL else 'OFF'}")
    else:
        print(f"🔧 G-opt Fallback 모드 (DEPSM)")
        print(f"   G-opt Fallback: {'활성화' if ENABLE_CPE_GOPT else '비활성화'}")
        print(f"   기본 CPE 옵션: {DEFAULT_CPE_OPTION}")
        print(f"   G-opt 임계값: {G_OPT_THRESHOLD}")

    df_cpe_k_depsm = cpe_regression_with_ridge_or_gopt_depsm(
        df_rawdata,
        default_cpe_option=DEFAULT_CPE_OPTION,
        enable_gopt=ENABLE_CPE_GOPT,
        exclude_outliers=True,
        process_mode=PROCESS_MODE,
        enable_span_check=ENABLE_RIDGE_SPAN_CONTROL
    )
    df_cpe_k_depsm.to_csv(os.path.join(results_dir, 'CPE_K_depsm.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE_K_depsm.csv 저장")

 


    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} " + "="*70)
    print("Step 6: DEPSM용 CPE K Fitting (보정 효과 확인)")
    print("="*70)
    print(f"Fitting 옵션: {DEFAULT_CPE_FIT_OPTION}")
    print("CPE K 계수를 측정 포인트에 fitting하여 보정 예측값 계산")

    df_cpe_fit_depsm = fit_cpe_k_to_measurements_depsm(
        df_rawdata,
        df_cpe_k_depsm,
        cpe_fit_option=DEFAULT_CPE_FIT_OPTION
    )

    # CPE_Fit.csv 별도 저장
    df_cpe_fit_depsm.to_csv(os.path.join(results_dir, 'CPE_Fit_depsm.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CPE_Fit_depsm.csv 저장")

    # df_rawdata에 컬럼 추가
    df_rawdata = pd.concat([df_rawdata, df_cpe_fit_depsm], axis=1)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} df_rawdata에 ideal psm용 CPE fitting 컬럼 추가 완료")

    ''' 
    # RawData_with_CPE_depsm.csv 저장
    df_rawdata.to_csv(os.path.join(results_dir, 'RawData_with_CPE_depsm.csv'), index=False)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} RawData_with_CPE_depsm.csv 저장 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IDEAL PSM용 CPE Fitting 완료\n")
    '''

    # Delta PSM
    df_rawdata = delta_psm(df_rawdata)
    df_rawdata.to_csv(os.path.join(results_dir, 'RawData_with_CPE_depsm.csv'), index=False)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Delta PSM 완료.')
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '모든 작업이 완료되었습니다.')





 



if __name__ == '__main__':
    main()

