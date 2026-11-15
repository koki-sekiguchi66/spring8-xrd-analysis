# -*- coding: utf-8 -*-
"""
Created on Wed Dec 18 12:10:51 2024

@author: harad
"""

import numpy as np 
import matplotlib.pyplot as plt 
from scipy.special  import voigt_profile 
import pandas as pd 
import lmfit

'F:\\修士データ\\SP8\\diffraction data\\1.0C\\93CR\\fitting_results.csv'
'F:\\修士データ\\SP8\\diffraction data\\1.0C\\93CR\\bcg_removed\\harada10C93cr_0001bcg.csv'


# Voigt関数の定義
def voigt(x, amp1, center1, width1, amp2, center2, width2, amp3, center3, width3):
    y = amp1 * voigt_profile(x - center1, width1, width1) \
        + amp2 * voigt_profile(x - center2, width2, width2) \
        + amp3 * voigt_profile(x - center3, width3, width3)
    return y

# CSVファイルの読み込み（ヘッダーなし）
data = pd.read_csv('F:\\修士データ\\SP8\\diffraction data\\1.0C\\93CR\\fitting_results.csv', header=None)
x = data[0].values
y = data[1].values

# xの範囲指定
x_min = 11
x_max = 12.5

# 範囲内のデータをフィルタリング
mask = (x >= x_min) & (x <= x_max)
x_filtered = x[mask]
y_filtered = y[mask]

# モデルとパラメータの定義
model = lmfit.Model(voigt)
params = model.make_params(amp1=1, center1=-2, width1=1, amp2=2, center2=0, width2=1, amp3=1, center3=3, width3=0.5)

# パラメータの制約
params['amp1'].min = 0
params['amp2'].min = 0
params['amp3'].min = 0

# フィッティング
result = model.fit(y_filtered, params, x=x_filtered)

# フィッティング結果の計算
fitted_y = result.best_fit

# 各Voigt関数の寄与を計算
components = result.eval_components(x=x_filtered)

# フィッティング結果をCSVファイルに出力
output_data = pd.DataFrame({0: x_filtered, 1: y_filtered, 2: fitted_y})
output_data.to_csv('F:\\修士データ\\SP8\\diffraction data\\1.0C\\93CR\\bcg_removed\\harada10C93cr_0001bcg.csv', index=False, header=False)

# フィッティング結果のプロット
plt.figure()
plt.plot(x_filtered, y_filtered, label='Experimental data')
plt.plot(x_filtered, fitted_y, label='Fitted data', linestyle='--')
for i, (name, comp) in enumerate(components.items()):
    plt.plot(x_filtered, comp, label=f'Voigt {i+1}', linestyle=':')
plt.legend()
plt.show()

