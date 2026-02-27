import numpy as np
import pandas as pd
import bigdataquery as bdq
from datetime import datetime

# 2
# =========================
# 설정값
# =========================
days = 6  # 추출할 데이터 일수
exclude_recent_days = 1  # 최근 N일 데이터 제외 (일부 테이블 적재 지연 대응, 0이면 제외 없음)
expo_days = 10 # expo_overlay_lot 추출할 데이터 일수 (days보다 기간길게 설정)

# 필터링 조건 (필요시 수정)
target_lotid = None   # 특정 LOT ID로 필터링 (예: "B0K421.1"), None이면 전체
#target_lotid = "(\'B0K486.1\',\'B0K271.1\')"   # 특정 LOT ID로 필터링 (예: "B0K421.1"), None이면 전체
target_pstepseq = 'VC075030' # None  # 특정 Photo Step으로 필터링 (예: "VC075030"), None이면 전체
target_mstepseq = 'VC075040' # None  # 특정 Metro Step으로 필터링 (예: "VC075040"), None이면 전체

print(f"설정: {days}일치 데이터 추출 (최근 {exclude_recent_days}일 제외)")
if target_lotid:
    print(f"LOT ID 필터: {target_lotid}")
if target_pstepseq:
    print(f"Photo STEP 필터: {target_pstepseq}")
if target_mstepseq:
    print(f"Metro STEP 필터: {target_mstepseq}")

# APC 테이블용 DB_USER (섹션 8: PSM Input 추출에 사용)
DB_USER_APC = "EAPCP2"
