# -*- coding: utf-8 -*-
"""
Created on Fri May 23 15:19:39 2025

@author: harad
"""


from scipy.ndimage import median_filter
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


#入力-----------------------------------------------------------------------------

root_dir = Path(r"F:\修士データ\SP8\diffraction data\20250517")
folders = os.listdir(root_dir)

window_size = 51  # ノイズ除去用の median filter のウィンドウ（奇数）
rolling_window = 101  # rolling minimum のウィンドウサイズ（奇数）

for h in range(len(folders)):
    print(folders[h])
    

    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{root_dir}\\{folders[h]}\\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{root_dir}\\{folders[h]}\\bcg_removed4\\'
    #--------------------------------------------------------------------------------


    # 処理ファイルのリスト取得
    all_file = os.listdir(in_path) 
    cont_all_file = len(all_file)
    
    # フォルダが存在しなければ作成
    if not os.path.exists(out_path):
        os.makedirs(out_path)
        

    for i in range(cont_all_file):
        in_file_path = os.path.join(in_path, all_file[i])
        data = np.loadtxt(in_file_path)
        x = data[:, 0]
        y = data[:, 1]
    
        # 10.5°以上の範囲取得
        valid_indices = x > 10.5
        indices = np.where(valid_indices)[0]
    
        # ステップ1: ノイズ除去
        y_denoised = np.copy(y)
        y_denoised[indices] = median_filter(y[indices], size=window_size)
    
        # ステップ2: Rolling Minimum 推定
        bg_vals = y_denoised[indices]
        pad = rolling_window // 2
        bg_rolled = np.array([
            np.min(bg_vals[max(i - pad, 0): min(i + pad + 1, len(bg_vals))])
            for i in range(len(bg_vals))
        ])
    
        # ステップ3: 単調減少化
        for j in range(1, len(bg_rolled)):
            if bg_rolled[j] > bg_rolled[j - 1]:
                bg_rolled[j] = bg_rolled[j - 1]
    
        # バックグラウンド配列へ反映
        y_background = np.zeros_like(y)
        y_background[indices] = bg_rolled
    
        # ステップ4: バックグラウンド除去
        y_corrected = y - y_background
    
        # ==== 全体プロット ====
        plt.figure(figsize=(8, 5))
        plt.plot(x, y, label='Raw Data', alpha=0.6)
        plt.plot(x, y_background, label='Estimated Background (Rolling Min)', linestyle='dashed', color='g')
        plt.plot(x, y_corrected, label='Corrected Data', color='r')
        plt.legend()
        plt.xlabel('2θ (degrees)')
        plt.ylabel('Intensity')
        plt.ylim(0, 300)
        plt.title(f'XRD Background Subtraction: {all_file[i]}')
        plt.show()
    
        # ==== 20–21度の範囲を拡大 ====
        plt.figure(figsize=(8, 5))
        plt.plot(x, y, label='Raw Data', alpha=0.6)
        plt.plot(x, y_background, label='Estimated Background', linestyle='dashed', color='g')
        plt.plot(x, y_corrected, label='Corrected Data', color='r')
        plt.legend()
        plt.xlabel('2θ (degrees)')
        plt.ylabel('Intensity')
        plt.xlim(20, 21)
        plt.ylim(0, 300)
        plt.title(f'Zoomed in: 20–21° ({all_file[i]})')
        plt.show()
    
        # 出力ファイル作成
        out_file = np.column_stack([x, y_corrected])
        filename = os.path.splitext(all_file[i])[0]
        out_file_path = os.path.join(out_path, filename + "bcg.csv")
        np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
    
        print(f"Saved: {out_file_path}")
