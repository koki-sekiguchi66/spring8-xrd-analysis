# -*- coding: utf-8 -*-
"""
Created on Tue Dec 16 14:53:40 2025

@author: harad
"""


import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from pathlib import Path
from pybaselines.whittaker import arpls 
from scipy.interpolate import PchipInterpolator


#処理したい複数のフォルダの入っているフォルダのアドレス。F:\adress\処理したいフォルダ\tth　の構造になっていないといけない
root_dir = Path(r"H:\diffraction data\1.0C_bests")

th_min = 10.2

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

def rubberband_filter(x_anchors, y_anchors):
    """
    アンカーポイント群の下側包絡線（lower convex hull）を見つける関数。
    
    Args:
        x_anchors (list): アンカーのx座標
        y_anchors (list): アンカーのy座標
        
    Returns:
        (list, list): フィルタリング後のx, y座標
    """
    # 点が2つ未満ならそのまま返す
    if len(x_anchors) < 3:
        return x_anchors, y_anchors

    final_x = [x_anchors[0]]
    final_y = [y_anchors[0]]
    
    current_idx = 0
    while current_idx < len(x_anchors) - 1:
        min_slope = float('inf')
        best_next_idx = -1
        
        # 現在の点から見て、最も傾きが小さい点を探す
        for i in range(current_idx + 1, len(x_anchors)):
            dx = x_anchors[i] - x_anchors[current_idx]
            dy = y_anchors[i] - y_anchors[current_idx]
            
            if dx > 0: # xが増加していることを確認
                slope = dy / dx
                if slope < min_slope:
                    min_slope = slope
                    best_next_idx = i
        
        # 最適な次の点が見つかったら、それを採用して更新
        if best_next_idx != -1:
            current_idx = best_next_idx
            final_x.append(x_anchors[current_idx])
            final_y.append(y_anchors[current_idx])
        else:
            # 次の点が見つからなければ終了
            break
            
    return final_x, final_y

#入力-----------------------------------------------------------------------------

folders = os.listdir(root_dir)
for h in range(len(folders)):
    print(folders[h])
    
    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{root_dir}\\{folders[h]}\\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{root_dir}\\{folders[h]}\\bcg_removed_arpls\\'
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
        # --- データの切り出し ---
        # x > th_min のデータだけを完全に抽出
        mask = data[:, 0] > th_min
        x_sub = data[mask, 0]
        y_sub = data[mask, 1]
        
        # --- Step 1: スパイクノイズを除去 ---
        # 切り出した y_sub に対してのみ処理を行う
        y_despiked = remove_spikes(y_sub, threshold_factor=5)
        
        # --- Step 2: 谷を探す ---
        # y_despiked は x > th_min の範囲のみなので、インデックスもこの範囲内でのものになる
        minima_indices, _ = find_peaks(-y_despiked, distance=100)
        
        # --- Step 3: アンカーポイントを作成 ---
        x_anchors = []
        y_anchors = []
        valley_avg_window = 11 
        
        # y_despiked の長さに基づいた端点処理
        candidate_indices = np.concatenate(([0], minima_indices, [len(y_despiked)-1]))
        candidate_indices = np.unique(candidate_indices)
        
        for idx in candidate_indices:
            half_window = valley_avg_window // 2
            start = max(0, idx - half_window)
            end = min(len(y_despiked), idx + half_window + 1)
            
            # x_sub, y_despiked を使って平均を出す
            x_anchors.append(np.mean(x_sub[start:end]))
            y_anchors.append(np.mean(y_despiked[start:end]))
        
        # --- Step 4: rubber band法 ---
        monotonic_x, monotonic_y = rubberband_filter(x_anchors, y_anchors)
        
        # --- Step 5: PCHIP補間でバックグラウンド生成 ---
        if len(monotonic_x) >= 2:
            pchip_model = PchipInterpolator(monotonic_x, monotonic_y)
            # x_sub（8.5度以上）の範囲だけで補間をかける
            y_background_final = pchip_model(x_sub)
        else:
            print(f"警告: アンカー不足。arplsで代替します。")
            y_background_final = arpls(y_despiked, lam=1e7)[0]
        
        # バックグラウンド除去（ここも 8.5度以上の範囲のみ）
        y_corrected_sub = y_despiked - y_background_final
        
        # --- 最終的なデータの扱い ---
        # 最終的に 8.5度以上のデータだけで良い場合：
        final_x = x_sub
        final_y = y_corrected_sub
        
        # もし「元の全データ長を維持しつつ、8.5度以下は元の値を残したい」場合：
        # y_final = np.copy(data[:, 1])
        # y_final[mask] = y_corrected_sub
    
        # --- 以下、プロットと保存 ---
        plt.figure(figsize=(8, 5))
        plt.plot(final_x, final_y, label='Raw Data', alpha=0.3)
        plt.plot(final_x, y_despiked, label='Despiked Data', color='cyan', alpha=0.6)
        plt.plot(monotonic_x, monotonic_y, 'o', color='orange', label='Monotonic Anchors')
        plt.plot(final_x, y_background_final, label='Final BG (PCHIP)', linestyle='dashed', color='g')
        plt.plot(final_x, y_corrected_sub, label='Corrected Data', color='r')
        plt.legend()
        plt.ylim(-100, 500)
        plt.title(f'Robust PCHIP Method: {all_file[i]}')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.show()
        
        # --- 出力ファイル作成 (最終的な補正データを出力) ---
        out_file = np.column_stack([final_x, y_corrected_sub])
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
        out_file_path = os.path.join(out_path, filename + "bcg.csv")
        np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
        print(f"Saved: {out_file_path}")
    """    
                
