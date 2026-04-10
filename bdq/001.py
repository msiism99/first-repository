import numpy as np
import pandas as pd
import bigdataquery as bdq
from datetime import datetime

days = 3
exclude_recent_days = 2
expo_days = 4

target_lotid = None   
#target_lotid = "(\'B0K486.1\',\'B0K271.1\')"
target_pstepseq = 'VC075030'
target_mstepseq = 'VC075040'
target_mstepseq_oco = 'VC077251'

DB_USER_APC = "EAPCP2"
db_user = "SIMAXP2"
