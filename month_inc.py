import pandas as pd
import math

inf = 1.07
inte = 1.025
B10,B15,Bx2 = 1.1,1.15,2**0.25
df1 = pd.DataFrame({
    'old': [x for x in range(40, 101)],
    'year': [x for x in range(25, 86)],
    'infle': [inf**x for x in range(0, 61)],
    'B21_13': [120000*math.exp(1.269564 * ((x+1)**0.5 - 1)) for x in range(0, 61)],
    'B21_10': [120000*math.exp(1.19847 * ((x+1)**0.5 - 1)) for x in range(0, 61)]
})

df1['normalization_ms'] = df1['B21_13']/df1['infle']
df1['normalization_msi'] = df1['B21_10']/df1['infle']
df1['MS_month_inc'] = df1['normalization_ms']*(inte-1)/12*10
df1['MSI_month_inc'] = df1['normalization_msi']*(inte-1)/12*10
df1['B21_13'] = df1['B21_13'].astype('int64')
df1['B21_10'] = df1['B21_10'].astype('int64')
df1['normalization_ms'] = df1['normalization_ms'].astype('int64')
df1['normalization_msi'] = df1['normalization_msi'].astype('int64')
df1['MS_month_inc'] = df1['MS_month_inc'].astype('int64')
df1['MSI_month_inc'] = df1['MSI_month_inc'].astype('int64')
print(df1[0:20])
print(df1[20:40])
print(df1[40:60])
