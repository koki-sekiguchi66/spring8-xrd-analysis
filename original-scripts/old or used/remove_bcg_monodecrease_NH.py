# -*- coding: utf-8 -*-
"""
Created on Sat Feb 15 23:25:51 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

#入力-----------------------------------------------------------------------------

CR="90CR"
C_content="1.0C"
folder_path="F:\修士データ\SP8\diffraction data\\1.0C\\90CR"


# 処理したいtthファイルの入っているファイルパス
in_path = fr'{folder_path}\\tth\\'
# 処理後のcsvファイルを出力するファイルパス
out_path = fr'{folder_path}\bcg_removed3\\'
#--------------------------------------------------------------------------------

# 処理ファイルのリスト取得
all_file = os.listdir(in_path) 
cont_all_file = len(all_file)

# フォルダが存在しなければ作成
if not os.path.exists(out_path):
    os.makedirs(out_path)

for i in range(cont_all_file):
    # tthファイルの読み込み（2列: 2θ, 強度）
    in_file_path = os.path.join(in_path, all_file[i])
    data = np.loadtxt(in_file_path)  
    x = data[:, 0]  # 2θ（角度）
    y = data[:, 1]  # 強度

    # ガウシアンフィルターを適用（バックグラウンドの推定）
    sigma = 70  # 平滑化の強さ（調整可能）
    background_filtered = gaussian_filter(y, sigma=sigma)

    # **バックグラウンドを単調減少に修正**
    for j in range(1, len(background_filtered)):
        if background_filtered[j] > background_filtered[j - 1]:  # 増加を防ぐ
            background_filtered[j] = background_filtered[j - 1]

    # バックグラウンドを除去
    y_corrected = y - background_filtered

    # **全体プロット**
    plt.figure(figsize=(8,5))
    plt.plot(x, y, label='Raw Data', alpha=0.6)
    plt.plot(x, background_filtered, label='Estimated Background (Monotonic)', linestyle='dashed', color='g')
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity')
    plt.title(f'XRD Background Subtraction: {all_file[i]}')
    plt.show()

    # **20-21度の範囲を拡大**
    plt.figure(figsize=(8,5))
    plt.plot(x, y, label='Raw Data', alpha=0.6)
    plt.plot(x, background_filtered, label='Estimated Background (Monotonic)', linestyle='dashed', color='g')
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity')
    plt.xlim(20, 21)  # 20-21度にズーム
    plt.ylim(0, 300)  # y軸の範囲を0〜300に設定
    plt.title(f'Zoomed in: 20-21° ({all_file[i]})')
    plt.show()

    # 出力ファイル作成
    out_file = np.column_stack([x, y_corrected])
    filename = os.path.splitext(all_file[i])[0]  # 拡張子を除いたファイル名取得
    out_file_path = os.path.join(out_path, filename + "bcg.csv")
    np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')

    print(f"Saved: {out_file_path}")
