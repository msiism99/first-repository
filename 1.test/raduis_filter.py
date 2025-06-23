import pandas as pd
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def filter_by_radius(input_path, output_path, radius_threshold):
    """
    RawData 파일에서 radius가 특정 threshold를 초과하는 행을 필터링합니다.
    
    :param input_path: 입력 CSV 파일 경로 (예: 'RawData-1.csv')
    :param output_path: 필터링된 결과를 저장할 경로 (예: 'Filtered_RawData-1.csv')
    :param radius_threshold: 필터링 기준이 되는 radius 값
    """
    try:
        # 데이터 로드
        logging.info(f"Loading data from {input_path}")
        df_rawdata = pd.read_csv(input_path)

        # radius 필터링
        logging.info(f"Applying radius filter: {radius_threshold}")
        df_filtered = df_rawdata[df_rawdata['radius'] <= radius_threshold]
        num_removed = len(df_rawdata) - len(df_filtered)
        logging.info(f"Filtered out {num_removed} rows exceeding the radius threshold.")

        # 필터링된 데이터 저장
        df_filtered.to_csv(output_path, index=False)
        logging.info(f"Filtered data saved to {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"Error during radius filtering: {e}")
        raise e

