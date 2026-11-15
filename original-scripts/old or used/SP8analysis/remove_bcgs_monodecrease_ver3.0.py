# -*- coding: utf-8 -*-
"""
Created on Tue Oct 14 18:21:29 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from pathlib import Path
from sklearn.isotonic import IsotonicRegression

#入力-----------------------------------------------------------------------------

root_dir = Path(r"H:\test\a")


try:        
    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{root_dir}\\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{root_dir}\\bcg_removed_mono\\'
    #--------------------------------------------------------------------------------

    # 処理ファイルのリスト取得
    all_file = os.listdir(in_path) 
    cont_all_file = len(all_file)
    
    # フォルダが存在しなければ作成
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    

    for i in range(cont_all_file):
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
        
            sigma = 70
            valid_indices = x > 10.5
        
            y_background = np.copy(y)
        
            # 8.5度以上の部分だけガウシアンフィルタで平滑化
            y_filtered = gaussian_filter(y[valid_indices], sigma=sigma)
        
            # --- ▼▼▼ ここからが修正箇所 ▼▼▼ ---
        
            # Isotonic Regression を使用して、滑らかで単調減少するバックグラウンドを推定
            # 1. Isotonic Regressionのインスタンスを作成（単調減少を指定）
            ir = IsotonicRegression(increasing=False)
        
            # 2. 対象領域のxと、ガウシアン平滑化後のyでモデルを学習・変換
            #    scikit-learnの仕様上、xは2次元配列にする必要があります
            x_valid = x[valid_indices].reshape(-1, 1)
            y_smoothed_monotonic = ir.fit_transform(x_valid, y_filtered)
        
            # 3. 計算されたバックグラウンドを元のy_background配列の対応する位置に戻す
            y_background[valid_indices] = y_smoothed_monotonic
        
            # --- ▲▲▲ 修正箇所ここまで ▲▲▲ ---
            # 元の単調減少処理ループは不要になるので削除します
        
            # バックグラウンド除去
            y_corrected = y - y_background
        
            # ==== 全体プロット ====
            plt.figure(figsize=(8, 5))
            plt.plot(x, y, label='Raw Data', alpha=0.6)
            plt.plot(x, y_background, label='Estimated Background (Isotonic)', linestyle='dashed', color='g')
            plt.plot(x, y_corrected, label='Corrected Data', color='r')
            plt.legend()
            plt.xlabel('2θ (degrees)')
            plt.ylabel('Intensity')
            # plt.ylim(0, 1000) # y軸の範囲はデータに合わせて自動調整させる方が良い場合もある
            plt.title(f'XRD Background Subtraction: {all_file[i]}')
            plt.grid(True, linestyle='--', alpha=0.6)
            plt.show()
        
            # 出力ファイル作成
            out_file = np.column_stack([x, y_corrected])
            filename = os.path.splitext(all_file[i])[0]
            out_file_path = os.path.join(out_path, filename + "_bcg.csv")
            np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
        
            print(f"Saved: {out_file_path}")
        
except:
    print("error")
