# -*- coding: utf-8 -*-
"""
Created on Thu Apr 17 17:10:49 2025

@author: harad
"""

# background を差し引くプログラム

#仮想環境(今回はtest)でpybeadsをpipインストールして、仮想環境上でspyderを開くこと
#https://work-life-enj.com/spyder-virtual-environment/

import matplotlib.pyplot as plt
import numpy as np
import pybeads
import os 

folder_path="F:\修士データ\SP8\diffraction data\\20250710"

files = os.listdir(folder_path)


for i in range(len(files)):
    

    #入力-----------------------------------------------------------------------------
    
    CR="90CR"
    C_content="0.5C"

    
    
    # 処理したいtthファイルの入っているファイルパス
    in_path = fr'{folder_path}\{files[i]}\tth\\'
    # 処理後のcsvファイルを出力するファイルパス
    out_path = fr'{folder_path}\{files[i]}\bcg_removed\\'
    #--------------------------------------------------------------------------------
    
    #処理ファイルの名前リストと数
    all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
    cont_all_file = len(all_file)
    
    # フォルダが存在しなければ作成
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    
        for i in range(0, cont_all_file):
            #ファイルの読み込み
            in_file_path = in_path + all_file[i]
            in_file = np.loadtxt(in_file_path, dtype = 'float')
            
            #回折角thと強度Inをそれぞれ一次元配列に格納
            th = np.empty([0])
            In = np.empty([0])
            
            for j in range(0, len(in_file)):
                th = np.append(th, in_file[j][0])
                In = np.append(In, in_file[j][1])
            
            # バックグラウンドフィッテング　https://qiita.com/skotaro/items/d943bc9a50da9410e9cb
            fc = 0.006 # ハイパスフィルター作成に使うcutoff周波数
            d = 1 # ハイパスフィルター作成時のパラメータ。1でよい。詳細は論文参照。
            r = 6 # 非対称ペナルティの非対称具合
            
            # 測定データとその微分にかかる正規化パラメータ
            amp = 0.8
            lam0 = 0.5 * amp
            lam1 = 5 * amp
            lam2 = 4 * amp
            # MMアルゴリズムのループ回数
            Nit = 15
            # ペナルティー関数
            pen = 'L1_v2'
            
            #処理後データIn_signal_est, バックグラウンド
            In_signal_est, bg_est, cost = pybeads.beads(In, d, fc, r, Nit, lam0, lam1, lam2, pen, conv=None)
            # バックグラウンドフィッテング終わり*******************************************************************************
            
            out_file = np.column_stack([th,In_signal_est]) # https://output-zakki.com/numpy-joining-arrays/
            filename = all_file[i].split('.') 
            out_file_path = out_path + filename[0] +"bcg" + ".csv"
            np.savetxt(out_file_path, out_file, delimiter=',' ,fmt='%.5f')
            print(out_file_path)
        
        
        """
        グラフの出力  https://www.yutaka-note.com/entry/matplotlib_pyplot#%E7%B7%9A%E3%81%AE%E7%A8%AE%E9%A1%9Eline
        plt.figure()
        # Figureの作成
        fig = plt.figure()
        # Axesの作成
        ax = fig.subplots(2, 1)
        # 折れ線グラフのプロット
        ax[0].plot(th, In,'b-',  label='all')
        ax[0].plot(th, bg_est,'r--', label='bcg')
        
        ax[1].plot(th, In_signal_est,'r-')
        
        
        
        ax[0].set_xlim(9, 35)
        ax[0].set_ylim(-100, 1000)
        ax[1].set_xlim(9, 35)
        ax[1].set_ylim(-100, 1000)
        
        ax[0].set(xlabel="2theta",ylabel="Intensity")
        ax[1].set(xlabel="2theta",ylabel="Intensity")
        ax[0].legend()
        plt.show()
        """