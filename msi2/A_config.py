FOLDER_PATH = 'C:/users/sungil.moon/Desktop/8Y40M/code/ORIGIN/nau'
RESULT = 'C:/users/sungil.moon/Desktop/8Y40M/code/ORIGIN/RESULT'

DEFAULT_OSR_OPTION = '19para'
DEFAULT_CPE_OPTION = '15para'
DEFAULT_CPE_FIT_OPTION = '38para'

NORM_FACTOR = 150000.0

PROCESS_MODE_FUNCTIONS = {
    'ADI': lambda group: (group['raw_x'].values, group['raw_y'].values),
    'OCO': lambda group: (group['X_reg'].values, group['Y_reg'].values)
}
