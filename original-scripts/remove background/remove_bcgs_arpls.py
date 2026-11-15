# -*- coding: utf-8 -*-
"""
Created on Mon Oct 20 15:28:03 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from pybaselines.whittaker import arpls 


#処理したい複数のフォルダの入っているフォルダのアドレス。F:\adress\処理したいフォルダ\tth　の構造になっていないといけない
root_dir = Path(r"H:\diffraction data\0.8C_bests\test")


# --- 以下はメインの処理 ---

def remove_spikes(y, threshold_factor=7):
    """
    下向きのスパイクノイズを検出し、近傍の平均値で置き換える関数。
    
    Args:
        y (np.array): 強度データ
        threshold_factor (float): ノイズと判断する閾値の係数
        
    Returns:
        np.array: スパイク除去後の強度データ
    """
    y_corrected = np.copy(y)
    diffs = np.abs(np.diff(y))
    median_diff = np.median(diffs) # 差分の絶対値の中央値（ノイズレベルの指標）
    threshold = median_diff * threshold_factor

    for i in range(1, len(y) - 1):
        # 前後の点両方から閾値以上低い点をスパイクと判断
        is_spike = (y[i] < y[i-1] - threshold) and (y[i] < y[i+1] - threshold)
        if is_spike:
            # 前後の点の平均値で置き換え
            y_corrected[i] = (y[i-1] + y[i+1]) / 2
            
    return y_corrected


#入力-----------------------------------------------------------------------------

folders = os.listdir(root_dir)
for h in range(len(folders)):
    print(folders[h])
    
    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{root_dir}\\{folders[h]}\\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{root_dir}\\{folders[h]}\\bcg_removed_arpls_unsmoothed\\'
    # 処理ファイルのリスト取得
    all_file = os.listdir(in_path)
    cont_all_file = len(all_file)

    # フォルダが存在しなければ作成
    if not os.path.exists(out_path):
        os.makedirs(out_path)

    for i in range(len(all_file)):
        in_file_path = os.path.join(in_path, all_file[i])
        try:
            data = np.loadtxt(in_file_path)
        except Exception as e:
            print(f"ファイルを読み込めませんでした: {in_file_path}, エラー: {e}")
            continue
            
    # --- forループ内 ---
        x = data[:, 0]
        y = data[:, 1]
    
        # --- Step 1: スパイクノイズを除去 ---
        # threshold_factorでスパイク検出の感度を調整
        y_despiked = remove_spikes(y, threshold_factor=3)
    

        y_background, params = arpls(y, lam=1e8)
    
        # バックグラウンド除去
        y_corrected = y_despiked - y_background
    
        # --- 以下、プロットと保存 ---
        plt.figure(figsize=(8, 5))
        plt.plot(x, y, label='Raw Data', alpha=0.3)
        plt.plot(x, y_despiked, label='Despiked Data', color='cyan', alpha=0.6)
        plt.plot(x, y_background, label='Final BG (PCHIP)', linestyle='dashed', color='g')
        plt.plot(x, y_corrected, label='Corrected Data', color='r')
        plt.legend()
        plt.ylim(-100, 500)
        plt.title(f'Robust PCHIP Method: {all_file[i]}')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.show()
        
        # --- 出力ファイル作成 (最終的な補正データを出力) ---
        out_file = np.column_stack([x, y_corrected])
        filename = os.path.splitext(all_file[i])[0]
        out_file_path = os.path.join(out_path, filename + "bcg.csv")
        np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
        print(f"Saved: {out_file_path}")
        
    """
        # --- 拡大プロット ---
        plt.figure(figsize=(8, 5))
        plt.plot(x, y_corrected, label='Corrected Data', color='r')
        plt.axhline(0, color='k', linestyle='--', label='Zero Line')
        plt.legend()
        plt.title(f'Zoomed-in Baseline Check: {all_file[i]}')
        plt.xlim(30, 35) # 確認する範囲はデータに合わせて調整してください
        plt.ylim(-200, 200)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.show()
    
        # --- 出力ファイル作成 (最終的な補正データを出力) ---
        out_file = np.column_stack([x, y_corrected])
        filename = os.path.splitext(all_file[i])[0]
        out_file_path = os.path.join(out_path, filename + "_bcg.csv")
        np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
        print(f"Saved: {out_file_path}")
    """    
                
