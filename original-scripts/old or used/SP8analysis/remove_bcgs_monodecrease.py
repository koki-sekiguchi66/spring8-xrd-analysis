# -*- coding: utf-8 -*-
"""
Created on Wed May 21 10:56:23 2025

@author: harad
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from pathlib import Path

#入力-----------------------------------------------------------------------------

root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251003\0.6C93CR")
folders = os.listdir(root_dir)
for h in range(len(folders)):
    print(folders[h])
    
    try:        
        # 処理したいtthファイルの入っているファイルパス
        in_path = fr'{root_dir}\\{folders[h]}\\tth\\'
        # 処理後のcsvファイルを出力するファイルパス
        out_path = fr'{root_dir}\\{folders[h]}\\bcg_removed_mono\\'
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
        
            sigma = 70
            valid_indices = x > 8.5
        
            y_background = np.copy(y)  # 元データをまずコピー
        
            # 10.5度以上の部分だけ平滑化
            y_filtered = gaussian_filter(y[valid_indices], sigma=sigma)
            y_background[valid_indices] = y_filtered
        
            # 単調減少処理は10.5度以上の部分だけ抽出して連続処理
            indices = np.where(valid_indices)[0]  # 10.5度以上のインデックスリスト
        
            for idx in range(1, len(indices)):
                cur = indices[idx]
                prev = indices[idx - 1]
                if y_background[cur] > y_background[prev]:
                    y_background[cur] = y_background[prev]
        
            # バックグラウンド除去
            y_corrected = y - y_background
        
            # ==== 全体プロット ====
            plt.figure(figsize=(8, 5))
            plt.plot(x, y, label='Raw Data', alpha=0.6)
            plt.plot(x, y_background, label='Estimated Background (Monotonic)', linestyle='dashed', color='g')
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
            plt.plot(x, y_background, label='Estimated Background (Monotonic)', linestyle='dashed', color='g')
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
            filename = os.path.splitext(all_file[i])[0]  # 拡張子を除いたファイル名取得
            out_file_path = os.path.join(out_path, filename + "bcg.csv")
            np.savetxt(out_file_path, out_file, delimiter=',', fmt='%.5f')
        
            print(f"Saved: {out_file_path}")
            
    except:
        print("error")
