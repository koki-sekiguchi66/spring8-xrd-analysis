# -*- coding: utf-8 -*-
"""
Created on Tue Oct 21 11:46:52 2025

@author: harad

"""
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import glob
import matplotlib.animation as animation

#指定したフォルダ内のtthが含まれるフォルダすべての動画を作成

# 🔧 パラメータ設定
offset = 500  # オフセット量
dpi = 200

fps = 10
interval = 1000/fps  # フレーム間隔（ミリ秒）

mask1_min = 10.5
mask1_max = 12.5
mask2_min = 18
mask2_max = 22

# ルートディレクトリを指定
#処理したい複数のフォルダが入っているフォルダパス

root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251114\tensile")
folders = os.listdir(root_dir)

print(f"処理対象フォルダ: {folders}")

# --- プロットやアニメーションに関する設定 ---
# グラフを重ねて描画する際のオフセット値
offset = 500
# アニメーションの解像度 (dots per inch)
dpi = 150
# アニメーションのフレーム間隔 (ミリ秒)
interval = 100
# アニメーションのフレームレート (frames per second)
fps = 10

# 各フォルダを順番に処理する
for h in range(len(folders)):
    print("--------------------------------------------------")
    print(f"フォルダ '{folders[h]}' の処理を開始します。")
    print("--------------------------------------------------")

    # 処理したいtthファイルの入っているフォルダパス
    in_path = root_dir / folders[h] / 'tth'

    # フォルダが存在しない場合はスキップ
    if not in_path.exists():
        print(f"警告: '{in_path}' が見つからないため、スキップします。")
        continue

    # ファイルを取得してソート
    tth_files = sorted(glob.glob(str(in_path / "*.tth")))
    
    # ファイルが見つからない場合はスキップ
    if not tth_files:
        print(f"警告: '{in_path}' に .tth ファイルが見つからないため、スキップします。")
        continue

    # 50の倍数番目のファイルのプロット用データ
    stacked_files = []
    # アニメーション用の全ファイルデータ
    file_list = []

    # 全てのtthファイルを1回だけループ処理
    for i, file in enumerate(tth_files, start=1):
        data = np.loadtxt(file)
        x = data[:, 0]
        y = data[:, 1]
        
        # 毎回全てのファイル情報をリストに追加
        file_list.append((x, y, os.path.basename(file)))

        # 50の倍数番目のファイルのみを処理
        if i % 50 == 0:
            # 1. 個別のサブプロットを作成
            mask1 = (x >= mask1_min) & (x <= mask1_max)
            mask2 = (x >= mask2_min) & (x <= mask2_max)

            fig, axes = plt.subplots(2, 1, figsize=(8, 6), dpi=100, sharex=False)
            fig.suptitle(f"File {i}: {os.path.basename(file)}", fontsize=14)

            axes[0].plot(x[mask1], y[mask1], color="blue")
            axes[0].set_title("Range: 10.5–12.5°")
            axes[0].set_ylabel("Intensity")

            axes[1].plot(x[mask2], y[mask2], color="green")
            axes[1].set_title("Range: 18.2–22°")
            axes[1].set_xlabel("2θ (degrees)")
            axes[1].set_ylabel("Intensity")

            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.show() # 個別のプロットを表示
            
            # 2. スタックプロット用にデータを追加
            stacked_files.append((x, y + len(stacked_files) * offset, os.path.basename(file)))

    # 50の倍数番目をまとめて描画
    if stacked_files:
        plt.figure(figsize=(12, 8), dpi=200)
        for x_stacked, y_stacked, label_stacked in stacked_files:
            plt.plot(x_stacked, y_stacked, label=label_stacked)
        plt.xlabel("2θ (degrees)")
        plt.ylabel("Intensity (with offset)")
        plt.title(f"Stacked Plot: Every 50th File in '{folders[h]}'")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left') # 凡例が重ならないように外側に配置
        plt.tight_layout()
        plt.show() # スタックプロットを表示

    # アニメーションを生成
    if file_list:
        fig, axes = plt.subplots(1, 2, figsize=(16, 6), dpi=dpi)
        line1, = axes[0].plot([], [], color='blue')
        line2, = axes[1].plot([], [], color='green')
    
    
        # setup_plot関数が、引数で最大値を受け取れるように変更
        def setup_plot(ax, title, xlabel="", ylabel=""):
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)

    
        # setup_plotを呼び出す際に、それぞれの最大値を渡す
        setup_plot(axes[0], "Range: 10.5–12.5°", ylabel="Intensity")
        setup_plot(axes[1], "Range: 18.2–22°", xlabel="2θ (degrees)")
        
        axes[0].set_xlim(mask1_min, mask1_max)
        axes[1].set_xlim(mask2_min, mask2_max)
    
        def init():
            line1.set_data([], [])
            line2.set_data([], [])
            return line1, line2

        def update(frame):
            x_anim, y_anim, label_anim = file_list[frame]
            
            # --- ここから追加 ---
            # 左グラフのy軸最大値を計算 (このフレームのデータのみ)
            mask_left = (x_anim >= mask1_min) & (x_anim <= mask1_max)
            y_in_range_left = y_anim[mask_left]
            # 範囲内にデータがあればその最大値、なければ1を最大値とする
            max_y_left_frame = np.max(y_in_range_left) if y_in_range_left.size > 0 else 1
            if max_y_left_frame == 0: max_y_left_frame = 1 # ゼロ除け
            axes[0].set_ylim(0, max_y_left_frame * 1.05) # y軸を更新

            # 右グラフのy軸最大値を計算 (このフレームのデータのみ)
            mask_right = (x_anim >= mask2_min) & (x_anim <= mask2_max)
            y_in_range_right = y_anim[mask_right]
            max_y_right_frame = np.max(y_in_range_right) if y_in_range_right.size > 0 else 1
            if max_y_right_frame == 0: max_y_right_frame = 1 # ゼロ除け
            axes[1].set_ylim(0, max_y_right_frame * 1.05) # y軸を更新
            # --- ここまで追加 ---

            line1.set_data(x_anim, y_anim)
            line2.set_data(x_anim, y_anim)
            fig.suptitle(f"File: {label_anim}", fontsize=14)
            
            # blit=Falseのため、line1, line2 だけでなく軸の更新も反映される
            return line1, line2

        ani = animation.FuncAnimation(
            fig, update, frames=len(file_list), init_func=init,
            blit=False, interval=interval # blit=TrueからFalseに変更
        )

        # MP4で保存
        save_path = root_dir / folders[h] / f'{folders[h]}_tth_animation.mp4'
        ani.save(str(save_path), writer="ffmpeg", fps=fps)
        print(f"アニメーションを '{save_path}' に保存しました。")
        plt.close(fig) # メモリ解放

print("\n全ての処理が完了しました。")