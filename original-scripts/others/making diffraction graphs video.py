# -*- coding: utf-8 -*-
"""
Created on Fri Jun 13 14:36:06 2025

@author: harad
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import glob
import os

# 🔧 パラメータ設定
folder_path = r"H:\diffraction data\0.3C_bests\90CR" 
offset = 500  # オフセット量
dpi = 200

fps = 5
interval = 1000/fps  # フレーム間隔（ミリ秒）


# ファイルを取得してソート
tth_files = sorted(glob.glob(os.path.join(f"{folder_path}\\tth\\", "*.tth")))



# 50の倍数番目のファイルのプロット用データ
stacked_files = []

frames = []
file_list = []    

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
        
    if i % 1 == 0:
        data = np.loadtxt(file)
        x = data[:, 0]
        y = data[:, 1]
        file_list.append((x, y, os.path.basename(file)))

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


# アニメーション用の初期化関数
fig, axes = plt.subplots(1, 2, figsize=(16, 9), dpi=dpi)
line1, = axes[0].plot([], [], color='blue')
line2, = axes[1].plot([], [], color='blue')
axes[0].set_title("Range: 11–12.5°")
axes[1].set_title("Range: 19–21°")
axes[0].set_ylabel("Intensity")
axes[1].set_xlabel("2θ (degrees)")
axes[1].set_ylabel("Intensity")

def init():
    line1.set_data([], [])
    line2.set_data([], [])
    return line1, line2

# フレームごとの更新
def update(frame):
    x, y, label = file_list[frame]
    mask1 = (x >= 10.5) & (x <= 13.7)
    mask2 = (x >= 18.2) & (x <= 22)
    line1.set_data(x[mask1], y[mask1])
    line2.set_data(x[mask2], y[mask2])
    fig.suptitle(f"File: {label}", fontsize=14)
    axes[0].relim()
    axes[0].autoscale_view()
    axes[1].relim()
    axes[1].autoscale_view()
    return line1, line2

# アニメーション生成
ani = animation.FuncAnimation(
    fig, update, frames=len(file_list), init_func=init,
    blit=False, interval=interval
)

# MP4で保存（要：ffmpeg）
ani.save(fr"{folder_path}//tth_animation.mp4", writer="ffmpeg", fps=fps)