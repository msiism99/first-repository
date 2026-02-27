# 7
# data_kind별로 분리
if len(df_rawdata) > 0:
    # RAWDATA: TEST, DieX, DieY, X_reg, Y_reg
    df_raw_rawdata = df_rawdata[df_rawdata['data_kind'] == 'RAWDATA'].copy()
    df_raw_rawdata = df_raw_rawdata.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'X_reg',
        'value_y': 'Y_reg'     # Point MRC사용하는 경우에는 순수계측값이 아님.  value_y = Y_reg - MRC_RY    (즉, 순수계측값에서 Point MRC를 뺴준값이   RAWDATA에서의 Value값임.)
    })
    
    # TEST: coordinate_X, coordinate_Y, MRC_RX, MRC_RY
    df_raw_test = df_rawdata[df_rawdata['data_kind'] == 'TESTDATA'].copy()
    df_raw_test = df_raw_test.rename(columns={
        'test_point_no': 'TEST',
        'value_x': 'coordinate_X',
        'value_y': 'coordinate_Y',
        'mrc_x_valn': 'MRC_RX',
        'mrc_y_valn': 'MRC_RY'
    })
    df_raw_test = df_raw_test[['lot_transn_seq', 'slot_id', 'TEST', 'coordinate_X', 'coordinate_Y', 'MRC_RX', 'MRC_RY']]
    
    # PERSHOTMRC: MRC_X, MRC_Y
    df_raw_pershotmrc = df_rawdata[df_rawdata['data_kind'] == 'PERSHOT'].copy()
    df_raw_pershotmrc = df_raw_pershotmrc.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'PSM_X',  
        'value_y': 'PSM_Y'        # PERSHOT에서의 value값은  PSM Input임.   (MRC_Y 랑 헷갈리면 안됨. )
    })
    df_raw_pershotmrc = df_raw_pershotmrc[['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY', 'PSM_X', 'PSM_Y']]
    
    print(f"✅ RAWDATA 분리 완료")
    print(f"  - RAWDATA: {len(df_raw_rawdata)} rows")
    print(f"  - TEST: {len(df_raw_test)} rows")
    print(f"  - PERSHOT: {len(df_raw_pershotmrc)} rows")
else:
    print("⚠️ RAWDATA가 없습니다.")
    df_raw_rawdata = pd.DataFrame()
    df_raw_test = pd.DataFrame()
    df_raw_pershotmrc = pd.DataFrame()
