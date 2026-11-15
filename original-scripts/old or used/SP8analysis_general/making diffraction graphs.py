# -*- coding: utf-8 -*-
"""
Created on Mon May 12 14:25:34 2025

@author: harad
"""

import numpy as np
import matplotlib.pyplot as plt
import glob
import os

# 🔧 パラメータ設定
folder_path = r"F:\修士データ\SP8\diffraction data\\1.0C\90CR\\tth\\" 
offset = 500  # オフセット量

# ファイルを取得してソート
tth_files = sorted(glob.glob(os.path.join(folder_path, "*.tth")))

# 50の倍数番目のファイルのプロット用データ
stacked_files = []

for i, file in enumerate(tth_files, start=1):  # 1始まりの番号
    data = np.loadtxt(file)
    x = data[:, 0]
    y = data[:, 1]

    # 2の倍数番目のファイル：2つの範囲をサブプロットで表示
    if i % 1 == 0:
        mask1 = (x >= 10.5) & (x <= 12.5)
        mask2 = (x >= 18.2) & (x <= 22)

        fig, axes = plt.subplots(2, 1, figsize=(8, 6), dpi=100, sharex=False)
        fig.suptitle(f"File {i}: {os.path.basename(file)}", fontsize=14)

        # 11–12.5°
        axes[0].plot(x[mask1], y[mask1], color="blue")
        axes[0].set_title("Range: 11–12.5°")
        axes[0].set_ylabel("Intensity")

        # 19–21°
        axes[1].plot(x[mask2], y[mask2], color="green")
        axes[1].set_title("Range: 19–21°")
        axes[1].set_xlabel("2θ (degrees)")
        axes[1].set_ylabel("Intensity")

        plt.tight_layout(rect=[0, 0, 1, 0.95])  # タイトルのスペース確保
        plt.show()


    # 50の倍数番目 → オフセット付きでまとめて描画
    if i % 50 == 0:
        stacked_files.append((x, y + len(stacked_files) * offset, os.path.basename(file)))

# 50の倍数番目をまとめて描画
if stacked_files:
    plt.figure(figsize=(10, 6), dpi=1000)
    for x, y, label in stacked_files:
        plt.plot(x, y, label=label)
    plt.xlabel("2θ (degrees)")
    plt.ylabel("Intensity")
    plt.title("Stacked Plot: Every 50th File")
    plt.legend()
    plt.tight_layout()
    plt.show()
