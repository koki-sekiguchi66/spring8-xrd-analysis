# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 17:50:36 2025

@author: harad
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import os 

#入力-----------------------------------------------------------------------------

CR="0CR"
C_content="0.5C"
folder_path="F:\\修士データ\\SP8\\diffraction data"


# 処理したいtthファイルの入っているファイルパス
in_path = f'{folder_path}\\{C_content}\\{CR}\\tth\\'
# 処理後のcsvファイルを出力するファイルパス
out_path = f'{folder_path}\\{C_content}\\{CR}\\bcg_removed2\\'
#--------------------------------------------------------------------------------

# 処理ファイルのリスト取得
all_file = os.listdir(in_path) 
cont_all_file = len(all_file)

for i in range(cont_all_file):
    # tthファイルの読み込み（2列: 2θ, 強度）
    in_file_path = os.path.join(in_path, all_file[i])
    data = np.loadtxt(in_file_path)  
    x = data[:, 0]  # 2θ（角度）
    y = data[:, 1]  # 強度

    # ピークを除いたバックグラウンド推定用データを作成
    peak_threshold = np.percentile(y, 60)  # 強度の上位40%をピークと判断
    mask = y < peak_threshold  # ピーク以外の部分をTrueとする
    y_bg = np.copy(y)
    y_bg[~mask] = np.nan  # ピーク部分をNaNにする

    # ガウシアンフィルターを適用（NaNを無視するために補完）
    sigma = 100  # 平滑化の強さ（調整可能）
    y_bg_filtered = gaussian_filter(np.nan_to_num(y_bg, nan=np.nanmean(y_bg)), sigma=sigma)

    # バックグラウンドを除去
    y_corrected = y - y_bg_filtered

    # プロット
    plt.figure(figsize=(8,5))
    plt.plot(x, y, label='Raw Data', alpha=0.6)
    plt.plot(x, y_bg_filtered, label='Estimated Background', linestyle='dashed', color='g')
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity')
    plt.title(f'XRD Background Subtraction: {all_file[i]}')
    plt.show()
    
    # **20-21度の範囲を拡大**
    plt.figure(figsize=(8,5))
    plt.plot(x, y, label='Raw Data', alpha=0.6)
    plt.plot(x, y_bg_filtered, label='Estimated Background', linestyle='dashed', color='g')  # 修正
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity')
    plt.xlim(20, 21)  # 20-21度にズーム
    plt.ylim(0, 300)  # y軸の最大値を300に設定
    plt.title(f'Zoomed in: 20-21° ({all_file[i]})')
    plt.show()

    # 出力ファイル作成
    out_file = np.column_stack([x, y_corrected])
    filename = os.path.splitext(all_file[i])[0]  # 拡張子を除いたファイル名取得
    out_file_path = os.path.join(out_path, filename + "bcg.csv")
    np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f', comments='')

    print(f"Saved: {out_file_path}")