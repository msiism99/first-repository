# stages 컬럼 설명표

`Stages_Columns_Code_Reference.xlsx`는 `MERGE/MRC_PSM_decorrect.ipynb`의 SQL과 계산식 기준 설명표입니다. Windows PC의 실제 파일을 읽은 결과는 아닙니다. 기본 정상 처리 경로에서 저장되는 76개 테이블, 608개 고유 컬럼, 3,157개의 파일별 컬럼 설명을 정리했습니다. 조건과 결측 처리에 따라 실제 컬럼 구성이 달라질 수 있습니다.

Excel 시트:

- `참고`: 표 기준, 단위, 입력 파일 선택과 해석
- `파일목록`: 단계/파일의 역할, 행 단위, 기본 전체 Parquet 위치
- `파일별컬럼`: 파일별 모든 컬럼의 설명, 단위·스케일, 생성식, 주의사항
- `컬럼사전`: 반복 컬럼 설명을 모은 사전. 파일에 따라 의미가 달라지는 설명도 포함
- `모델계수`: 기적용 CMP MRC, PSM72, TROCS72, wafer WK/RK, shot CPE38의 항과 스케일

## 실제 저장 파일의 컬럼 표 만들기

1. ZIP을 풀고 `Stages_Column_Dictionary.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 놓습니다.
2. 노트북을 열고 위에서 아래로 셀을 실행합니다.
3. 입력은 `C:\PHOTO_ANALYSIS\BASIC\output_decorrect_notebook\stages`입니다.
4. 결과는 새 `C:\PHOTO_ANALYSIS\BASIC\output_column_dictionary` 폴더에 저장합니다.

출력 파일:

- `stages_columns.xlsx`: 실제 파일목록/파일별컬럼/미등록컬럼/읽기오류/참고
- `stages_files.csv`: 실제 파일 목록
- `stages_columns.csv`: 실제 파일별 컬럼 설명
- `stages_unknown_columns.csv`: 설명에 등록되지 않은 컬럼

별도 Python 모듈이나 DB 연결 없이 노트북 하나로 실행합니다. pandas, pyarrow, openpyxl이 필요합니다. Parquet은 schema/footer만, Excel은 첫 행만 읽어 본문 전체를 메모리에 올리지 않습니다. Excel 자료형은 헤더만으로 확인할 수 없으므로 미검사로 기록합니다. 실패한 파일은 오류표에 기록하고 나머지 파일 검사를 계속합니다.

## 해석할 때 구분할 것

- `coordinate_x/y`: 원본 DB 좌표. RAWDATA/PERSHOT은 shot index로 사용합니다.
- `coordinate_X/Y`: 실측 mark의 shot-local 좌표(µm).
- `Coordinate_X/Y`: TROCS 생성 mark의 shot-local 좌표(µm).
- `pos_x/y_valn`: QUERY 파일은 mm, 가공 INPUT 파일은 µm.
- `wk1~20`, `rk3~20`: DB CMP의 기적용 MRC 계수.
- `mrc_k1~72_valn`: DB 기적용 PSM 계수.
- `rk1~72_valn`: DB 기적용 TROCS 계수.
- `21_*_RK_WAFER_COEFFICIENTS`의 `RK*_X/Y`: wafer 공통 WK/RK 재회귀 계수.
- `27_*_CPE_SHOT_COEFFICIENTS`의 `RK*_X/Y`: shot별 CPE38 재회귀 계수.
- `raw_x/y`: MRC/PSM decorrect 후 값. 최초 RAWDATA와 다른 가공 단계입니다.
- `real_residual_x/y`: WK/RK와 shot CPE를 제거한 최종 residual.

측정값·보정값·residual의 단위는 입력 DB 측정값의 원단위를 유지합니다. 코드는 nm/µm 변환을 추가하지 않습니다. 계수는 원본 matrix의 스케일을 따르므로 `basis × beta`로 기여값을 해석하세요. Excel 이름의 `_sample_행수`는 일부 행만 저장된 파일을 뜻합니다.

노트북은 실제 커널에서 Parquet/Excel 검사, 단위·계수 구분, 빈 파일·미등록 컬럼·손상 파일 처리를 검증했습니다. 검증에는 합성 파일을 사용했습니다.
