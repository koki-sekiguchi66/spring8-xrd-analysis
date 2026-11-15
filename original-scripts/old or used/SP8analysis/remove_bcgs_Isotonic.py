# -*- coding: utf-8 -*-
"""
Created on Tue Oct 14 18:33:05 2025

@author: harad
"""


import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from pathlib import Path

def estimate_background(y, iterations=10, sigma=20):
    """
    反復クリッピング法を用いてバックグラウンドを推定する関数。

    Args:
        y (np.array): 強度データ
        iterations (int): 平滑化とクリッピングを繰り返す回数
        sigma (float): ガウシアン平滑化の強さ

    Returns:
        np.array: 推定されたバックグラウンド
    """
    # 元のデータのコピーで処理を開始
    background = np.copy(y)
    
    # 指定された回数だけ処理を繰り返す
    for _ in range(iterations):
        # 現在のバックグラウンドを平滑化
        smoothed = gaussian_filter(background, sigma=sigma)
        # 平滑化された曲線よりも値が小さい点を採用（ピークをクリッピング）
        background = np.minimum(background, smoothed)
        
    return background

#入力-----------------------------------------------------------------------------

root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251003")
folders = os.listdir(root_dir)
for h in range(len(folders)):
    print(folders[h])
    
    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{root_dir}\\{folders[h]}\\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{root_dir}\\{folders[h]}\\bcg_removed_mono2\\'
    # 処理ファイルのリスト取得
    all_file = os.listdir(in_path)
    cont_all_file = len(all_file)

    # フォルダが存在しなければ作成
    if not os.path.exists(out_path):
        os.makedirs(out_path)

    for i in range(cont_all_file):
        in_file_path = os.path.join(in_path, all_file[i])
        try:
            data = np.loadtxt(in_file_path)
        except Exception as e:
            print(f"ファイルを読み込めませんでした: {in_file_path}, エラー: {e}")
            continue
            
        x = data[:, 0]
        y = data[:, 1]

        # --- ▼▼▼ ここからが修正箇所 ▼▼▼ ---

        # 新しい関数を使ってバックグラウンドを推定
        # この2つのパラメータを調整することで、結果が大きく変わります
        sigma_val = 150  # 平滑化の強さ。以前より小さくする
        iter_val = 20   # 繰り返しの回数
        
        y_background = estimate_background(y, iterations=iter_val, sigma=sigma_val)

        # --- ▲▲▲ 修正箇所ここまで ▲▲▲ ---

        # バックグラウンド除去
        y_corrected = y - y_background


        # ==== 全体プロット ====
        plt.figure(figsize=(8, 5))
        plt.plot(x, y, label='Raw Data', alpha=0.6)
        plt.plot(x, y_background, label=f'Estimated BG (sigma={sigma_val}, iter={iter_val})', linestyle='dashed', color='g')
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
            
