print(df_BTC)
#print(df_ETH)
#print(df_XRP)
print(df_m3)
print(df_m4)
print(balance_coin)
print(balance_coin2)
print(balance_coin3)


target_exit = 180000
df_cal_BTC = df_BTC.copy()
df_cal_BTC['markPrice']=target_exit

print(balance_coin.iloc[0,1],round(df_cal_BTC['unRealizedProfit'].sum(),8),balance_coin.iloc[0,1]+round(df_cal_BTC['unRealizedProfit'].sum(),8))

values = list(range(112000, 180000, 1000))

for i in values:
    df_cal_BTC.loc[len(df_cal_BTC)] = ['BTCUSD_PERP',-100,i,target_exit,0]

df_cal_BTC['positionAmt'] = (df_cal_BTC['positionAmt'].astype(str).str.replace(',', '', regex=True).replace('nan', '0').astype(float))
df_cal_BTC['entryPrice'] = (df_cal_BTC['entryPrice'].astype(str).str.replace(',', '', regex=True).replace('nan', '0').astype(float))
df_cal_BTC['markPrice'] = (df_cal_BTC['markPrice'].astype(str).str.replace(',', '', regex=True).replace('nan', '0').astype(float))
df_cal_BTC['unRealizedProfit'] = df_cal_BTC['positionAmt']*100*(1/df_cal_BTC['entryPrice']-1/df_cal_BTC['markPrice'])

df_cal_BTC['positionAmt'] = df_cal_BTC['positionAmt'].map(lambda x: f"{x:.0f}")
df_cal_BTC['entryPrice'] = df_cal_BTC['entryPrice'].map(lambda x: f"{x:.3f}")
df_cal_BTC['markPrice'] = df_cal_BTC['markPrice'].map(lambda x: f"{x:.0f}")

print(df_cal_BTC)
print(balance_coin.iloc[0,1],round(df_cal_BTC['unRealizedProfit'].sum(),8),balance_coin.iloc[0,1]+round(df_cal_BTC['unRealizedProfit'].sum(),8))

# 251102    6.87693518 4.61279495 11.48973013




        symbol positionAmt  entryPrice   markPrice unRealizedProfit
0  BTCUSD_PERP       8,000   91037.832  110434.189       1.54342202
1  BTCUSD_PERP      -1,100  118206.950  110434.189       0.06549700
2  BTCUSD_PERP       4,200   96756.606  110434.189       0.53761881
3  BTCUSD_PERP      -1,200  108965.077  110434.189      -0.01465025
        symbol positionAmt  entryPrice   markPrice unRealizedProfit
0  BTCUSD_PERP       1,100  111848.981  110434.189      -0.01259940
1  BTCUSD_PERP        -200  113384.575  110434.189       0.00471249
        symbol positionAmt  entryPrice   markPrice unRealizedProfit
0  BTCUSD_PERP         700  109336.994  110434.189       0.00636078
1  BTCUSD_PERP        -200  115076.850  110434.189       0.00730643
  asset        balance        current
0   BTC     6.87693518     9.00882276
1   ETH    12.37566174    14.88645687
2   XRP 19697.46582204 20807.33486584
  asset    balance    current
0   BTC 0.85410488 0.84621797
  asset    balance    current
0   BTC 0.55094499 0.56461220
        bonds  price    EA     value
0  LONG_bonds   9410  1923  18095430
1         S&P  24280   400   9712000
2        INDO  14080   500   7040000
3       TOP10  31465    60   1887900
4        TSLA    457    10      4566
5        COIN    344    10      3438
6        MSTR    270    10      2695





6.87693518 2.13188758 9.008822760000001
         symbol positionAmt  entryPrice markPrice  unRealizedProfit
0   BTCUSD_PERP        8000   91037.832    180000        4.34311104
1   BTCUSD_PERP       -1100  118206.950    180000       -0.31946023
2   BTCUSD_PERP        4200   96756.606    180000        2.00745555
3   BTCUSD_PERP       -1200  108965.077    180000       -0.43460361
4   BTCUSD_PERP        -100  112000.000    180000       -0.03373016
..          ...         ...         ...       ...               ...
67  BTCUSD_PERP        -100  175000.000    180000       -0.00158730
68  BTCUSD_PERP        -100  176000.000    180000       -0.00126263
69  BTCUSD_PERP        -100  177000.000    180000       -0.00094162
70  BTCUSD_PERP        -100  178000.000    180000       -0.00062422
71  BTCUSD_PERP        -100  179000.000    180000       -0.00031037

[72 rows x 5 columns]
6.87693518 4.61279495 11.48973013
