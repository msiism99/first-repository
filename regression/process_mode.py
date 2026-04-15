# process_mode.py
PROCESS_MODE_FUNCTIONS = {
    'ADI': lambda group: (group['raw_x'].values, group['raw_y'].values),
    'OCO': lambda group: (group['X_reg'].values, group['Y_reg'].values)
}
