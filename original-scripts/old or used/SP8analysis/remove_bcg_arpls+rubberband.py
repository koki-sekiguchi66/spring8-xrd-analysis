# -*- coding: utf-8 -*-
"""
Created on Wed Oct 15 10:24:21 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from pathlib import Path
from pybaselines.whittaker import arpls # --- 追加箇所 ---
from scipy.interpolate import PchipInterpolator



root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251003\0.5C95CR")
# --- 以下はメインの処理 ---
# 処理したいtthファイルの入っているファイルパス
in_path = fr'{root_dir}\\tth\\'
# 処理後のcsvファイルを出力するファイルパス
out_path = fr'{root_dir}\\bcg_removed_mono3\\'

def remove_spikes(y, threshold_factor=5):
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
        
# --- forループ内 ---
    x = data[:, 0]
    y = data[:, 1]

    # --- Step 1: スパイクノイズを除去 ---
    # threshold_factorでスパイク検出の感度を調整
    y_despiked = remove_spikes(y, threshold_factor=5)

    # --- Step 2: スパイク除去後のデータから谷を探す ---
    # distanceはピーク間の最小距離（データ点数）
    minima_indices, _ = find_peaks(-y_despiked, distance=100)

    # --- Step 3: 谷周辺の平均値を計算してアンカーポイントを作成 ---
    x_anchors = []
    y_anchors = []
    # 谷周辺の平均化に使う窓のサイズ（奇数を推奨）
    valley_avg_window = 11 

    # データの両端をアンカーの候補に追加
    candidate_indices = np.concatenate(([0], minima_indices, [len(y)-1]))
    candidate_indices = np.unique(candidate_indices)

    for idx in candidate_indices:
        half_window = valley_avg_window // 2
        start = max(0, idx - half_window)
        end = min(len(y), idx + half_window + 1)
        
        # 窓内の平均x, yをアンカーとする
        x_anchors.append(np.mean(x[start:end]))
        y_anchors.append(np.mean(y_despiked[start:end]))

# --- Step 4: 輪ゴム法で不要なアンカーポイントを除去 ---
    monotonic_x, monotonic_y = rubberband_filter(x_anchors, y_anchors)

    # --- Step 5: PCHIP補間で最終的なバックグラウンドを生成 ---
    if len(monotonic_x) >= 2:
        pchip_model = PchipInterpolator(monotonic_x, monotonic_y)
        y_background_final = pchip_model(x)
    else:
        # アンカーが不足する場合はarplsで代替処理
        print(f"警告: {all_file[i]}でアンカーが不足。arplsで代替します。")
        y_background_final = arpls(y_despiked, lam=1e7)[0]
    
    # バックグラウンド除去
    y_corrected = y_despiked - y_background_final

    # --- 以下、プロットと保存 ---
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, label='Raw Data', alpha=0.3)
    plt.plot(x, y_despiked, label='Despiked Data', color='cyan', alpha=0.6)
    plt.plot(monotonic_x, monotonic_y, 'o', color='orange', label='Monotonic Anchors')
    plt.plot(x, y_background_final, label='Final BG (PCHIP)', linestyle='dashed', color='g')
    plt.plot(x, y_corrected, label='Corrected Data', color='r')
    plt.legend()
    plt.ylim(-100, 500)
    plt.title(f'Robust PCHIP Method: {all_file[i]}')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.show()
    
    # --- 出力ファイル作成 (最終的な補正データを出力) ---
    out_file = np.column_stack([x, y_corrected])
    filename = os.path.splitext(all_file[i])[0]
    out_file_path = os.path.join(out_path, filename + "_bcg.csv")
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