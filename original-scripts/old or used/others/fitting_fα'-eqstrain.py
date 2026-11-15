# -*- coding: utf-8 -*-
"""
Created on Wed Jan 28 14:23:15 2026

@author: harad
"""

import matplotlib.pyplot as plt
from lmfit import Model
import pandas as pd
import numpy as np

# 1. データの読み込み
# CSVの場合
#df = pd.read_csv('data.csv')

# Excelの場合
# df = pd.read_excel('data.xlsx', sheet_name='Sheet1')

#クリップボードから
df = pd.read_clipboard()


# 2. 列の抽出（列名はファイルに合わせて変更してください）
# 歪みデータ（横軸）
eps_data = df['strain'].values
# マルテンサイト分率データ（縦軸）
f_alpha_data = df['martensite_fraction'].values

# モデル関数の定義
def martensite_kinetics(epsilon, fs, beta, epsilon0, n):
    # epsilon0（開始歪）以下のときは0を返す
    res = 1 - np.exp(-beta * np.maximum(0, epsilon - epsilon0)**n)
    return fs * res

# モデルオブジェクトの作成
model = Model(martensite_kinetics)

# パラメータの初期値設定
# fs: 飽和分率（1.0に固定することが多い）
# beta, epsilon0, n: 実験データに合わせて推測
params = model.make_params(fs=1.0, beta=0.2, epsilon0=0.5, n=1.3)

# fs を 1.0 に固定したい場合は以下を有効にする
params['fs'].set(vary=False)
params['epsilon0'].set(min=0.3)

# 3. フィッティング実行
result = model.fit(f_alpha_data, params, epsilon=eps_data)

# 4. 結果の表示
print(result.fit_report())

# 5. グラフで確認
plt.scatter(eps_data, f_alpha_data, label='Experimental Data')
plt.plot(eps_data, result.best_fit, 'r-', label='Best Fit')
plt.xlabel('Strain')
plt.ylabel('Martensite Fraction')
plt.legend()
plt.show()