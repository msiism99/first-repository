''' 
250321 update
config.py 파일 추가
- nau 파일이 저장된 기본 폴더 경로
- 추가로 관리할 설정 (예: radius_threshold, max_index 등)
'''

''' 
※ 돌리기전 주의사항
1. nau 저장폴더 설정.  기본 : 'C:/py_data/nau/2lot'
2. Edge Clear 위해서 radius_threshold 설정해여함. 기본 150000 설정되어 있음.
3. Zernike 분석시 max_index 설정해야함. 기본 64 설정되어 있음.

'''


# design_matrix_config 에 설정된 기본 옵션들을 import
from config import DEFAULT_OSR_OPTION, DEFAULT_CPE_OPTION, DEFAULT_CPE_FIT_OPTION

from config import FOLDER_PATH, RADIUS_THRESHOLD, MAX_INDEX, OUTLIER_THRESHOLD, DMARGIN_X, DMARGIN_Y, OUTLIER_SPEC_RATIO

import pandas as pd
from datetime import datetime
import os
import logging
import glob
import xlwings as xw


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_log.log"),
        logging.StreamHandler()
    ]
)

from nau_processor import (
    remove_duplicate_files,
    process_nau_file,
    save_combined_data
)

from calc_regression import (
    kmrc_decorrect,
    wk_rk_input_decorrect,
    remove_psm_add_pointmrc,
    multi_lot_regression_and_fitting,
    detect_outliers_studentized_residual,  # outlier 판정용 추가 
    reorder_coefficients,
    psm_decorrect,
    resi_to_cpe,
    cpe_k_to_fit,
    ideal_psm,
    delta_psm
)

from zernike_analysis_adi import zernike_analysis
from raduis_filter import filter_by_radius  

def main():
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

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 시작")
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.nau'):
            file_path = os.path.join(folder_path, file_name)
            try:
                rawdata_df, trocs_input_df, psm_input_df, mrc_df, wk_rk_input_df = process_nau_file(file_path)
                rawdata_list.append(rawdata_df)
                trocs_input_list.append(trocs_input_df)
                psm_input_list.append(psm_input_df)
                mrc_list.append(mrc_df)
                wk_rk_input_list.append(wk_rk_input_df)
                print(f"{file_name} 처리 완료")
            except Exception as e:
                print(f"{file_name} 처리 중 에러 발생: {e}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 시작")
    save_combined_data(rawdata_list, trocs_input_list, psm_input_list, mrc_list, wk_rk_input_list)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 완료")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 작업 완료")

    ############################### 2. raduis_filter ######################################## 
    # config에 정의된 RADIUS_THRESHOLD 사용
    # RawData 파일 필터링 (results 폴더 내 파일 사용)
    input_path = os.path.join(results_dir, "RawData-1.csv")
    filtered_data_path = os.path.join(results_dir, "Radius_Filtered_RawData-1.csv")
    radius_threshold = RADIUS_THRESHOLD  # 원하는 radius 임계값 설정.  config.py에서 가져온 값
    
    print("Starting radius filtering...")
    filter_by_radius(input_path, filtered_data_path, radius_threshold)

    ############################### 3. calc_regression ########################################

    # 데이터 로드 (results 폴더 내 파일)
    df_rawdata = pd.read_csv(filtered_data_path)
    df_wk_rk_input = pd.read_csv(os.path.join(results_dir, "WK_RK_INPUT.csv"))
    '''
    # 코드 추가!!
    mrc_df = pd.read_csv('C:/Users/sungil.moon/Desktop/250602_xlwings/results/MRC.csv')
    print(1)

    site22 = glob.glob('C:/Users/sungil.moon/Desktop/250602_xlwings/results/MTFF2.xlsx')
    wb22 = xw.Book(site22[0])
    ws22 = wb22.sheets['Sheet2']
    data22 = ws22.range('A1').options(expand='table').value
    mtff_gpm = pd.DataFrame(data22[1:], columns=[data22[0]])
    
    
    print(2)
    mrc_df['GPM'] = mtff_gpm['GPM']
    print(3)
    mrc_df.to_csv('C:/Users/sungil.moon/Desktop/250602_xlwings/results/MRC.csv', index=False)
    print(4)
    '''
    df_mrc_input = pd.read_csv(os.path.join(results_dir, "MRC.csv"))
    
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

    
    # 회귀 분석 및 예측 수행 (kmrc 옵션 적용)
    df_coeff = multi_lot_regression_and_fitting(df_rawdata, osr_option=DEFAULT_OSR_OPTION)


    ################################### outlier 판정용 추가 ######################################################################
    # outlier 판정
    # config.py에 정의된 상수를 사용하여 outlier 판정 수행
    df_rawdata = detect_outliers_studentized_residual(
        df_rawdata,
        threshold=OUTLIER_THRESHOLD,
        group_col='UNIQUE_ID',
        dmargin_x=DMARGIN_X,
        dmargin_y=DMARGIN_Y,
        outlier_spec_ratio=OUTLIER_SPEC_RATIO
    )    
    ########################################################################################################

    # 회귀 계수의 컬럼 순서 재정렬
    df_coeff = reorder_coefficients(df_coeff)

    # 회귀 계수 저장 (results 폴더에 저장)
    df_coeff.to_csv(os.path.join(results_dir, 'OSR_K.csv'), index=False)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'OSR Regression 및 Fitting 완료.')

     # PSM Decorrect (psm 옵션 적용)
    df_psm_input = pd.read_csv(os.path.join(results_dir, 'PerShotMRC.csv'))
    df_psm_de = psm_decorrect(df_rawdata, df_psm_input, cpe_fit_option=DEFAULT_CPE_FIT_OPTION)
    df_rawdata = pd.concat([df_rawdata, df_psm_de], axis=1)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'PSM Decorrect 완료.')
    



    # 추가 코드! TROCS INPUT Decorrect #######################
    #df_trocs_input = pd.read_csv(os.path.join(results_dir, 'Trocs_Input.csv'))
    #df_trocs_de = psm_decorrect(df_rawdata, df_trocs_input, cpe_fit_option=DEFAULT_CPE_FIT_OPTION)
    #df_rawdata2 = df_rawdata
    #df_rawdata2 = pd.concat([df_rawdata2, df_trocs_de], axis=1)
    #df_rawdata2.to_csv(os.path.join(results_dir, 'TROCS_decorrect.csv'), index=False) 
    #print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TROCS_INPUT Decorrect 완료.')

    #site1 = glob.glob('C:/Users/sungil.moon/Desktop/MTFF.xlsx')
    #wb11 = xw.Book(site1[0])
    #ws11 = wb11.sheets['Sheet']
    #data11 = ws11.range('A1').options(expand='table').value
    #df11 = pd.DataFrame(data11[1:], columns=data11[0])
    # 추가 코드! TROCS INPUT Decorrect #######################





    # CPE 19-parameter modeling (cpe 옵션 적용)
    #df_cpe_k = resi_to_cpe(df_rawdata, cpe_option=DEFAULT_CPE_OPTION)
    df_cpe_k = resi_to_cpe(df_rawdata, cpe_option='38para')
    df_cpe_k.to_csv(os.path.join(results_dir, 'RESI_TO_CPE.csv'), index=False)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'CPE Regression 완료.')

    
    # CPE fitting
    df_cpe_fit_res = cpe_k_to_fit(df_rawdata, df_cpe_k)
    df_rawdata = pd.concat([df_rawdata, df_cpe_fit_res], axis=1)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'CPE Fitting 완료.')

    # Ideal PSM
    df_rawdata = ideal_psm(df_rawdata)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Ideal PSM 완료.')

    # Delta PSM
    df_rawdata = delta_psm(df_rawdata)
    df_rawdata.to_csv(os.path.join(results_dir, 'Delta_PSM.csv'), index=False)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Delta PSM 완료.')
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '모든 작업이 완료되었습니다.')

    ############################### 4. zernike_analysis ########################################
    
    # Zernike 분석 실행 시 config에 정의된 MAX_INDEX 사용
    logging.info("Starting Zernike analysis")
    df_z_coeff, df_rawdata = zernike_analysis(df_rawdata, max_index=MAX_INDEX)

    # Z계수 nm단위로 결과 저장 (results 폴더에 저장)
    df_z_coeff.to_csv(os.path.join(results_dir, "Fringe_Zernike_Coefficients.csv"), index=False)
    logging.info("Zernike coefficients saved to Fringe_Zernike_Coefficients.csv")

    # Zernike Fitting 결과 저장 (예: "Zernike_Fit.csv")
    df_rawdata.to_csv(os.path.join(results_dir, "Zernike_Fit.csv"), index=False)
    logging.info("Zernike Fitting 결과 저장 완료.")

if __name__ == '__main__':
    main()
