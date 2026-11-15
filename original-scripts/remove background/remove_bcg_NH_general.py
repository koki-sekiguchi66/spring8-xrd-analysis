# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 17:50:36 2025

@author: harad
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import os 
from pathlib import Path

#入力-----------------------------------------------------------------------------

# 1. Pathオブジェクトとして定義（raw文字列 r を使うのが安全）
folder_path = Path(r"H:\test\test")

# 2. / 演算子で結合（自動で適切な区切り文字になります）
in_path = folder_path / "tth"
out_path = folder_path / "bcg_removed2"

# 3. 出力先フォルダがない場合に作成する処理（推奨）
out_path.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------
# 処理ファイルのリスト取得
# os.listdir の代わりに in_path.glob("*.tth") を使うとより便利です
all_file = list(in_path.glob("*.tth")) 
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
    plt.ylim(-100, 500)  # y軸の最大値を300に設定
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