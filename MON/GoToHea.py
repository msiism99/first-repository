import pandas as pd
import glob
import xlwings as xw

## Constant 20250501
first_B,first_E = 5.22048017, 12.38     # 0.14 to third
second_B,second_X = 2.38748477, 21023   # 0.06 to third
third_B = 1.19029866
third_B_1 = 0.43607052                  # 0.2 origin_mine / 0.08 dung-e / 0.15607052 mine
third_B_2 = 0.75422814                  # dung-e + 0.08440406
fourth_B = 0.5219
ENA_n = 40828
OND_n = 28850                           # 1324 * 7532.65   1533 * 19816.5   27349.15   
SUI_n = 1541

## Variable
SOUND,FIRST,SECOND,ENA,OND,SUI,wonwon,box,SOL = 119500, 4640, 3.24, 0.8, 1.06, 3.89, 3920900, 1383, 192

a11,a12,b11,b12 = 8000, -1200, 3000, -500
A11,A12,B11,B12 = 91037.8, 113049.3, 2878.16, 3831.14
a1,b1 = 4.56203128,12.31120735

a21,a22,c21,c22 = 3500, -900, 3000, -1000
A21,A22,C21,C22 = 94044.9, 106546.6, 2.2272, 2.5170
a2,c2 = 2.05796498,19954

a31,a32 = 1100, -400
A31,A32 = 110850.6, 114674.6
a3 = 1.21333852

a41,a42 = 700, -200
A41,A42 = 109336.9, 116860.4
a4 = 0.54520663


combined_df1 = pd.DataFrame([['SOUND',a11,A11,SOUND,0],
                        ['SOUND',a12,A12,SOUND,0],                   # 120689so
                        ['SOUND',a21,A21,SOUND,0],
                        ['SOUND',a22,A22,SOUND,0]],                  # 
                        columns = ['symbol','positionAmt','entryPrice','markPrice','unRealizedProfit'])

eth_df1 = pd.DataFrame([['FIRST',b11,B11,FIRST,0],                   # 3539.88Lo
                        ['FIRST',b12,B12,FIRST,0]],                  # 3831.14so_500
                        columns = ['symbol','positionAmt','entryPrice','markPrice','unRealizedProfit'])

xrp_df1 = pd.DataFrame([['SECON',c21,C21,SECOND,0],                  #
                        ['SECON',c22,C22,SECOND,0]],                 #
                        columns = ['symbol','positionAmt','entryPrice','markPrice','unRealizedProfit'])

BT_df2 = pd.DataFrame([['SOUND',a1,0],
                        ['SOUND',a2,0]],
                        columns = ['asset','balance','crossUnPnl'])

ET_df2 = pd.DataFrame([['FIRST',b1,0]],
                        columns = ['asset','balance','crossUnPnl'])

XR_df2 = pd.DataFrame([['SECON',c2,0]],
                        columns = ['asset','balance','crossUnPnl'])

combined_df3 = pd.DataFrame([['SOUND',a31,A31,SOUND,0],              # 
                             ['SOUND',a32,A32,SOUND,0]],             # 
                        columns = ['symbol','positionAmt','entryPrice','markPrice','unRealizedProfit'])

combined_df4 = pd.DataFrame([['SOUND',a3,0]],
                        columns = ['asset','balance','crossUnPnl']) 

combined_df5 = pd.DataFrame([['SOUND',a41,A41,SOUND,0],              # 
                             ['SOUND',a42,A42,SOUND,0]],             # 
                        columns = ['symbol','positionAmt','entryPrice','markPrice','unRealizedProfit'])

combined_df6 = pd.DataFrame([['SOUND',a4,0]],
                        columns = ['asset','balance','crossUnPnl']) 

combined_df1['unRealizedProfit'] = combined_df1['positionAmt']*100*(1/combined_df1['entryPrice']-1/combined_df1['markPrice'])
combined_df3['unRealizedProfit'] = combined_df3['positionAmt']*100*(1/combined_df3['entryPrice']-1/combined_df3['markPrice'])
combined_df5['unRealizedProfit'] = combined_df5['positionAmt']*100*(1/combined_df5['entryPrice']-1/combined_df5['markPrice'])
eth_df1['unRealizedProfit'] = eth_df1['positionAmt']*10*(1/eth_df1['entryPrice']-1/eth_df1['markPrice'])
xrp_df1['unRealizedProfit'] = xrp_df1['positionAmt']*10*(1/xrp_df1['entryPrice']-1/xrp_df1['markPrice'])

print(combined_df1)
print(eth_df1)
print(xrp_df1)
print(combined_df3)
print(combined_df5)

as_df = pd.DataFrame([['SOUND', round(BT_df2['balance'].sum(),8) + 0.35607052 + (combined_df4.iloc[0,1] - 1.19029866)/2 + 
                       + round(combined_df1['unRealizedProfit'].sum(),8) + round(combined_df3['unRealizedProfit'].sum(),8)/2,SOUND,0],
                      ['FIRST', ET_df2.iloc[0,1] + round(eth_df1['unRealizedProfit'].sum(),8) ,FIRST,0],
                      ['SECON', XR_df2.iloc[0,1] + round(xrp_df1['unRealizedProfit'].sum(),8) ,SECOND,0],
                      ['ONDO ', OND_n, OND, 0],
                      ['ETHEN', ENA_n, ENA, 0],
                      ['SUI  ', SUI_n, SUI, 0],
                      ['SOYMJ',0.08440406 + 0.83422814 + (combined_df4.iloc[0,1] - 1.19029866)/2 + round(combined_df3['unRealizedProfit'].sum(),8)/2,SOUND,0],
                      ['FIYMJ',1.62,FIRST,0],
                      ['FOYMJ',21.75,SOL,0],
                      ['SOMSI',0.11 + combined_df6.iloc[0,1] + round(combined_df5['unRealizedProfit'].sum(),8),SOUND,0]],
                        columns = ['asset','balance','price','wonhwa']) 

as_df['wonhwa'] = as_df['balance'] * as_df['price'] * box
as_df['wonhwa'] = as_df['wonhwa'].astype('int64')  # 먼저 정수형으로 변환
#as_df['wonhwa'] = as_df['wonhwa'].apply(lambda x: f"{x:,}")

print(as_df.to_string(formatters={'wonhwa': '{:,}'.format}))
print(as_df['wonhwa'].sum() - as_df.iloc[9,3] + wonwon, as_df["wonhwa"].iloc[0:6].sum(), as_df["wonhwa"].iloc[6:9].sum())
print(round(combined_df3['unRealizedProfit'].sum()/2+ (combined_df4.iloc[0,1] - 1.19029866)/2,8))
