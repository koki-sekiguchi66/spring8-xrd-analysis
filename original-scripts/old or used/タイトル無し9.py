# -*- coding: utf-8 -*-
"""
Created on Tue Feb 18 12:11:08 2025

@author: harad
"""


# peak fitting するプログラム

# Lmfitを仮想環境(今回はfitting1)にpip install する / matplotlib, pandas, openpyxlはconda install　
#https://qiita.com/mckeeeen/items/d4cbe4a16a102157f40c

#仮想環境(今回はfitting1)でspyderを開く
#https://work-life-enj.com/spyder-virtual-environment/

import tkinter as tk
from tkinter import filedialog
import pandas as pd
import numpy as np
import os
import math
import random
from lmfit.models import VoigtModel
import matplotlib.pyplot as plt

#入力-----------------------------------------------------------------------------

CR="90CR"
C_content="0.5C"
folder_path="F:\\卒論関連\\卒論実験データ\\SPring-8\\diffracion data"

#回折角の小さい順のピーク
peaks = ["fcc111", "bct011", "bct110"]

excel_sheet=""
for i in range(len(peaks)):
    print(peaks[i],end='')
    excel_sheet+=peaks[i]
    
# 処理したいファイルの入っているフォルダパス
#in_path = f'{folder_path}\\{C_content}\\{CR}\\bcg_removed\\220-\\'
#出力するファイルパス
out_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}output.xlsx'
#初期値（originでフィッテングした結果）の格納されたファイルパス
#init_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}_{excel_sheet}_initial.xlsx'

#-----------------------------------------------------------------------------


# GUIでファイルを選択
root = tk.Tk()
root.withdraw()  # Tkウィンドウを表示しない

# 初期値のExcelファイルを選択
init_path = filedialog.askopenfilename(title="初期値のExcelファイルを選択", filetypes=[("Excel files", "*.xlsx")])
if not init_path:
    print("初期値ファイルが選択されませんでした。処理を中止します。")
    exit()

# フィッティング対象のCSVファイルを選択（複数選択可）
file_paths = filedialog.askopenfilenames(title="フィッティングするCSVファイルを選択", filetypes=[("CSV files", "*.csv")])
if not file_paths:
    print("フィッティングファイルが選択されませんでした。処理を中止します。")
    exit()

# 初期値の読み込み
data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16, 17, 18], skiprows=[0])
data = data_pd.values
FWHM_initial = pd.read_excel(init_path, usecols=[7], skiprows=[0]).values[0][0]

# 初期値を辞書に格納
Init_pars = {'num': data[0][0]}
n = (len(data[0]) - 1) // 4  # ピーク数の推定

for s in range(1, n + 1):
    Init_pars[f'v{s}_center'] = data[0][4 * s - 3]
    Init_pars[f'v{s}_amplitude'] = data[0][4 * s - 2]
    Init_pars[f'v{s}_sigma'] = data[0][4 * s - 1] / (2 * math.sqrt(4 * math.log(2)))
    Init_pars[f'v{s}_gamma'] = data[0][4 * s] / 2

# 初期値リスト
prev_center = [float(Init_pars[f'v{s}_center']) for s in range(1, n + 1)]
prev_amplitude = [float(Init_pars[f'v{s}_amplitude']) for s in range(1, n + 1)]
prev_sigma = [float(Init_pars[f'v{s}_sigma']) for s in range(1, n + 1)]
prev_gamma = [float(Init_pars[f'v{s}_gamma']) for s in range(1, n + 1)]

# フィッティング範囲
th_min = Init_pars['v1_center'] - 0.3
th_max = Init_pars['v1_center'] + 0.6
ylim_max = Init_pars['v1_amplitude'] // FWHM_initial * 2

# 出力データを格納する変数
all_results = np.empty((0, 1 + n * 6), dtype=object)

# CSVファイルを順番に処理
for file_path in file_paths:
    print(f"処理中: {file_path}")

    # CSVファイルの読み込み
    df0 = pd.read_csv(file_path, header=None)
    in_file = df0.to_numpy()

    # フィッティング範囲のデータを抽出
    count_th = np.count_nonzero((in_file[:, 0] >= th_min) & (in_file[:, 0] <= th_max))
    th = np.empty((1, count_th), float)
    In = np.empty((1, count_th), float)

    u_th = 0
    for j in range(len(in_file)):
        if th_min <= in_file[j][0] <= th_max:
            th[0][u_th] = in_file[j][0]
            In[0][u_th] = in_file[j][1]
            u_th += 1

    # フィッティングモデルの作成
    voigt1 = VoigtModel(prefix='v1_')
    pars = voigt1.guess(In[0], x=th[0])
    pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0] * 0.97, max=prev_center[0] * 1.01)
    pars['v1_amplitude'].set(value=prev_amplitude[0], min=prev_amplitude[0] * 0.98, max=prev_amplitude[0] * 1.02)
    pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0] * 0.99, max=prev_sigma[0] * 1.02)
    pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0] * 0.99, max=prev_gamma[0] * 1.02)
    
    # 2つ目以降のピークの設定
    for k in range(2, n+1):
        pars.update(VoigtModel(prefix=f'v{k}_').make_params())
        pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=max(prev_center[k-1]-0.01, prev_center[k-2] + 0.05), max=prev_center[k-1]+0.05)  # 前のピークより大きい値にする
        pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=max(prev_amplitude[k-1]*0.98, 800), max=prev_amplitude[k-1]*1.1, vary=True)
        pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95, max=prev_sigma[k-1]*1.05)
        pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95, max=prev_gamma[k-1]*1.05)         
        
    mod = voigt1
    for l in range(2, n+1):
        mod += VoigtModel(prefix=f'v{l}_')

    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    
    # ループ後に prev_center, prev_sigma, prev_gamma を更新 
    
    prev_center = []
    prev_amplitude = []
    prev_sigma = []
    prev_gamma = []
    
    for r in range(1, n+1):
        prev_center.append(float(out.best_values.get(f'v{r}_center')))
        prev_amplitude.append(float(out.best_values.get(f'v{r}_amplitude')))
        prev_sigma.append(float(out.best_values.get(f'v{r}_sigma')))
        prev_gamma.append(float(out.best_values.get(f'v{r}_gamma')))
        Init_pars[f'v{r}_center'] = float(out.best_values.get(f'v{r}_center'))
        Init_pars[f'v{r}_amplitude'] = float(out.best_values.get(f'v{r}_amplitude'))
        Init_pars[f'v{r}_sigma'] = float(out.best_values.get(f'v{r}_sigma'))
        Init_pars[f'v{r}_gamma'] = float(out.best_values.get(f'v{r}_gamma'))
    mod = voigt1
    for k in range(2, n + 1):
        mod += VoigtModel(prefix=f'v{k}_')

    # フィッティング実行
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    residual_mean = np.mean(np.abs(out.residual))

    # 結果の格納
    cur_result = np.empty((1, 1 + n * 6), dtype=object)
    cur_result[0][0] = os.path.basename(file_path).replace("bcg.csv", "")
    for m in range(1, n + 1):
        cur_result[0][1 + (m - 1) * 6] = 0
        cur_result[0][2 + (m - 1) * 6] = out.best_values.get(f'v{m}_center')
        cur_result[0][3 + (m - 1) * 6] = out.best_values.get(f'v{m}_amplitude')
        cur_result[0][4 + (m - 1) * 6] = out.best_values.get(f'v{m}_sigma')*2*math.sqrt(4*math.log(2, math.e))
        cur_result[0][5 + (m - 1) * 6] = out.best_values.get(f'v{m}_gamma')*2
        cur_result[0][6 + (m - 1) * 6] = 1.0692 * out.best_values.get(f'v{m}_gamma') + math.sqrt(
            0.8664 * out.best_values.get(f'v{m}_gamma') ** 2 + 5.545083 * out.best_values.get(f'v{m}_sigma') ** 2)

    all_results = np.vstack((all_results, cur_result))

    # プロット
    fig, ax = plt.subplots(2, 1, dpi=130)
    ax[0].plot(th[0], In[0], 'o', label=str(os.path.basename(file_path).replace("bcg.csv", "")))
    ax[0].plot(th[0], out.best_fit, '-', label='best fit', zorder=10, lw=2)
    ax[1].plot(th[0], In[0], 'C6o', alpha=0.5)
    for p in range(1, n + 1):
        ax[1].plot(th[0], comps[f'v{p}_'], '--', label=f'component {p}')
    ax[0].set_xlim(th_min, th_max)
    ax[1].set_xlim(th_min, th_max)
    ax[0].legend()
    ax[1].legend()
    plt.show()
    
"""    
# 最終結果をExcelに保存
result_df = pd.DataFrame(all_results)
result_df.to_excel("fitting_results.xlsx", index=False)
print("フィッティング結果を 'fitting_results.xlsx' に保存しました。")
"""
#外部ファイルに出力
col = ['num', 'y0', '2th_'+ peaks[0], 'I_'+ peaks[0], 'wG'+peaks[0], 'wL'+peaks[0], 'FWHM_'+ peaks[0], 'y0', '2th_'+ peaks[1], 'I_'+ peaks[1], 'wG'+peaks[1], 'wL'+peaks[1], 'FWHM_'+ peaks[1], 'y0', '2th_'+ peaks[2], 'I_'+ peaks[2], 'wG'+peaks[2], 'wL'+peaks[2], 'FWHM_'+ peaks[2]]
df = pd.DataFrame(all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/

with pd.ExcelWriter(out_path, engine="openpyxl", mode='a', if_sheet_exists='new') as writer:
    df.to_excel(writer, sheet_name=excel_sheet + "refined", index=False)