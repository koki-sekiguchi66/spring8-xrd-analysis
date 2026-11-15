# -*- coding: utf-8 -*-
"""
Created on Tue Oct 14 18:38:08 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
# scipyのgaussian_filterは不要になります
from pathlib import Path
from pybaselines.whittaker import arpls # --- 追加箇所 ---


root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251003\0.5C95CR")
# --- 以下はメインの処理 ---
# 処理したいtthファイルの入っているファイルパス
in_path = fr'{root_dir}\\tth\\'
# 処理後のcsvファイルを出力するファイルパス
out_path = fr'{root_dir}\\bcg_removed_mono3\\'

if not os.path.exists(out_path):
    os.makedirs(out_path)

all_file = os.listdir(in_path)
for i in range(len(all_file)):
    in_file_path = os.path.join(in_path, all_file[i])
    try:
        data = np.loadtxt(in_file_path)
    except Exception as e:
        print(f"ファイルを読み込めませんでした: {in_file_path}, エラー: {e}")
        continue
        
    x = data[:, 0]
    y = data[:, 1]

    # --- ▼▼▼ ここからが修正箇所 ▼▼▼ ---

    # Asymmetrically Reweighted Penalized Least Squares (arpls) を使用
    # lamとpが調整パラメータです
    # lam: ベースラインの滑らかさ（大きいほど滑らかで直線的になる）
    y_background, params = arpls(y, lam=1e12)

    # --- ▲▲▲ 修正箇所ここまで ▲▲▲ ---

    # バックグラウンド除去
    y_corrected = y - y_background


    # ==== 全体プロット ====
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, label='Raw Data', alpha=0.6)
    plt.plot(x, y_background, label=f'Estimated BG (arpls)', linestyle='dashed', color='g')
    plt.plot(x, y_corrected, label='Corrected Data', color='r', linewidth=1.5)
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity')
    plt.title(f'XRD Background Subtraction: {all_file[i]}')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.show()

    # 出力ファイル作成
    out_file = np.column_stack([x, y_corrected])
    filename = os.path.splitext(all_file[i])[0]
    out_file_path = os.path.join(out_path, filename + "_bcg.csv")
    np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')

    print(f"Saved: {out_file_path}")
    
    # ==== 30-35度の範囲を拡大してベースラインを確認 ====
    plt.figure(figsize=(8, 5))
    # 補正後のデータのみプロット
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    # 比較のためのゼロラインを引く
    plt.axhline(0, color='k', linestyle='--', label='Zero Line')
    
    plt.legend()
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity (Corrected)')
    plt.title(f'Zoomed-in Baseline Check: {all_file[i]}')
    
    # X軸とY軸の範囲を限定
    plt.xlim(30, 35)
    plt.ylim(-200, 200) # yの範囲はデータのノイズレベルに応じて調整
    
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.show()