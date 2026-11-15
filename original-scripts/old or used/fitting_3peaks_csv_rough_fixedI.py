# -*- coding: utf-8 -*-
"""
Created on Wed Feb  5 20:13:35 2025

@author: harad
"""

# peak fitting するプログラム

# Lmfitを仮想環境(今回はfitting1)にpip install する / matplotlib, pandas, openpyxlはconda install　
#https://qiita.com/mckeeeen/items/d4cbe4a16a102157f40c

#仮想環境(今回はfitting1)でspyderを開く
#https://work-life-enj.com/spyder-virtual-environment/

import matplotlib.pyplot as plt
import numpy as np
import os 
from lmfit import Model
from lmfit.models import VoigtModel
import math
import pandas as pd
import random

#入力-----------------------------------------------------------------------------

CR="90CR"
C_content="0.5C"
folder_path="F:\\卒論関連\\卒論実験データ\\SPring-8\\diffracion data"

#ピークの数
n = 3
#回折角の小さい順のピーク
peaks = ["fcc111", "bct011", "bct110"]

excel_sheet=""
for i in range(len(peaks)):
    print(peaks[i],end='')
    excel_sheet+=peaks[i]
    
# 処理したいファイルの入っているフォルダパス
in_path = f'{folder_path}\\{C_content}\\{CR}\\bcg_removed\\test2\\'
#出力するファイルパス
out_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}output.xlsx'
#初期値（originでフィッテングした結果）の格納されたファイルパス
init_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}_{excel_sheet}_initial.xlsx'

#--------------------------------------------------------------------------------

#初期値の読み込み
data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16, 17, 18], skiprows=[0]) # https://note.nkmk.me/python-pandas-read-excel/
data = data_pd.values # https://note.nkmk.me/python-pandas-numpy-conversion/
FWHM_initial=pd.read_excel(init_path, usecols=[7], skiprows=[0]).values[0][0]

#初期値
Init_pars = {}
Init_pars['num'] = data[0][0]
for s in range(1,n+1):
    Init_pars[f'v{s}_center'] = data[0][4*s-3]
    Init_pars[f'v{s}_amplitude'] = data[0][4*s-2]
    Init_pars[f'v{s}_sigma'] = data[0][4*s-1]/(2*math.sqrt(4*math.log(2, math.e)))
    Init_pars[f'v{s}_gamma'] = data[0][4*s]/2

# すべてのピークの強度の合計を求める
total_I = sum(Init_pars[f'v{k}_amplitude'] for k in range(1, n+1))

#フィッテングする回折角2thetaの範囲の最小値
th_min = Init_pars['v1_center']-0.3
#フィッテングする回折角2thetaの範囲の最大値
th_max = Init_pars['v1_center']+0.5

#プロットのy軸の最大値
ylim_max = Init_pars['v1_amplitude']//FWHM_initial*2

#処理ファイルの名前リストと数
all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
cont_all_file = len(all_file)


#出力データを格納する変数の定義
all_results = np.empty((1,1+n*3), float) # https://pyming.info/2022/02/10/numpy_empty/
cur_result = np.empty((1,1+n*3), float)

# すべてのファイルで共通のピーク強度を見つけるための変数
best_v1_amplitude = None
best_total_residual = float('inf')
best_results = None

rough_best_v1_amplitude = 820
residual_limit = 175

prev_center = []
prev_sigma = []
prev_gamma = []

# 1つ目のピークの強度を変化させながら最適値を探索

for vib in range(-20, 20, 1):
    
    #初期値
    Init_pars = {}
    Init_pars['num'] = data[0][0]
    for s in range(1,n+1):
        Init_pars[f'v{s}_center'] = data[0][4*s-3]
        Init_pars[f'v{s}_amplitude'] = data[0][4*s-2]
        Init_pars[f'v{s}_sigma'] = data[0][4*s-1]/(2*math.sqrt(4*math.log(2, math.e)))
        Init_pars[f'v{s}_gamma'] = data[0][4*s]/2
        
    vib_I = vib * 5  # 1つ目のピークの増加分
    v1_new_amplitude = rough_best_v1_amplitude + vib_I  # 1つ目のピークの強度（全ファイル共通）
    
    total_residual = 0  # すべてのファイルの残差の合計
    
    # 差の2乗の合計
    diff_squared_sum_center = 0
    diff_squared_sum_amplitude = 0
    diff_squared_sum_sigma = 0
    diff_squared_sum_gamma = 0
    
    all_results = np.empty((0, 1 + n * 3), dtype=object)  # 初期化
    
    for i in range(cont_all_file):
    
        # 初期値をリストに追加
        if i == 0:
            prev_center = []
            prev_amplitude = []
            prev_sigma = []
            prev_gamma = []
            for q in range(1, n+1):
                # numpy.float64 ではなく float に変換

                prev_center.append(float(Init_pars[f'v{q}_center']))
                prev_amplitude.append(float(Init_pars[f'v{q}_amplitude']))
                prev_sigma.append(float(Init_pars[f'v{q}_sigma']))
                prev_gamma.append(float(Init_pars[f'v{q}_gamma']))
                
        # 処理したいファイルの読み込み
        in_file_path = in_path + all_file[i]
        in_file = np.loadtxt(in_file_path, delimiter=",", dtype='float')

        # number of theta data 
        count_th = np.count_nonzero((in_file >= th_min) & (in_file <= th_max), axis=0)[0]

        # 回折角thと強度Inをそれぞれ2次元配列に格納
        th = np.empty((1, count_th), float)
        In = np.empty((1, count_th), float)

        u_th = 0
        for j in range(len(in_file)):
            if (in_file[j][0] >= th_min) and (in_file[j][0] <= th_max):
                th[0][u_th] = in_file[j][0]
                In[0][u_th] = in_file[j][1] 
                u_th += 1 
                

        
        # 残りのピークの強度合計
        remaining_intensity = total_I - v1_new_amplitude

        if i == 0:#１つめだけ初期値を修正
            
            voigt1 = VoigtModel(prefix='v1_')
            pars = voigt1.guess(In[0], x=th[0])
            
            pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
            pars['v1_amplitude'].set(value=v1_new_amplitude, min=v1_new_amplitude*0.97, max=v1_new_amplitude*1.03)  # 1つ目のピークの強度を固定
            pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97, max=prev_sigma[0]*1.03)
            pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97, max=prev_gamma[0]*1.03)

            # 2つ目以降のピークの設定
            for k in range(2, n+1):
                pars.update(VoigtModel(prefix=f'v{k}_').make_params())

                # th の大小関係を固定
                pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=prev_center[k-1]*0.9 and prev_center[k-2] + 0.05, max=prev_center[k-1]*1.1)  # 前のピークより大きい値にする

                # 2つ目のピークの強度を自由に変化させる
                if k == 2:
                    pars[f'v2_amplitude'].set(value=Init_pars[f'v2_amplitude'], min=max(prev_amplitude[k-1]*0.9, prev_amplitude[k]), max=prev_amplitude[k-1]*1.1 and remaining_intensity - 200, vary=True)
            
                # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
                elif k == 3:
                    pars[f'v3_amplitude'].set(expr=f'{remaining_intensity} - v2_amplitude', vary=False)
            
                else:
                    pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

                pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95, max=prev_sigma[k-1]*1.05)
                pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95, max=prev_gamma[k-1]*1.05)         
                
            mod = voigt1
            for l in range(2, n+1):
                mod += VoigtModel(prefix=f'v{l}_')

            init = mod.eval(pars, x=th[0])
            out = mod.fit(In[0], pars, x=th[0])
            comps = out.eval_components(x=th[0])
            
            # ループ後に prev_center, prev_sigma, prev_gamma を更新 
            
            prev_center = []
            prev_amplitude = []
            prev_sigma = []
            prev_gamma = []
            
            for r in range(1, n+1):
                prev_center.append(float(out.best_values.get(f'v{r}_center')))
                prev_amplitude.append(float(out.best_values.get(f'v{r}_amplitude')))
                prev_sigma.append(float(out.best_values.get(f'v{r}_sigma')))
                prev_gamma.append(float(out.best_values.get(f'v{r}_gamma')))
                Init_pars[f'v{r}_center'] = float(out.best_values.get(f'v{r}_center'))
                Init_pars[f'v{r}_amplitude'] = float(out.best_values.get(f'v{r}_amplitude'))
                Init_pars[f'v{r}_sigma'] = float(out.best_values.get(f'v{r}_sigma'))
                Init_pars[f'v{r}_gamma'] = float(out.best_values.get(f'v{r}_gamma'))
            
            
        #フィッティング開始    
            
        voigt1 = VoigtModel(prefix='v1_')
        pars = voigt1.guess(In[0], x=th[0])
        
        pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
        pars['v1_amplitude'].set(value=v1_new_amplitude, min=v1_new_amplitude*0.98, max=v1_new_amplitude*1.02)  # 1つ目のピークの強度を固定
        pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97, max=prev_sigma[0]*1.03)
        pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97, max=prev_gamma[0]*1.03)

        # 2つ目以降のピークの設定
        for k in range(2, n+1):
            pars.update(VoigtModel(prefix=f'v{k}_').make_params())

            # th の大小関係を固定
            pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=prev_center[k-1]*0.97 and prev_center[k-2] + 0.05, max=prev_center[k-1]*1.03)  # 前のピークより大きい値にする

            # 2つ目のピークの強度を自由に変化させる
            if k == 2:
                pars[f'v2_amplitude'].set(value=Init_pars[f'v2_amplitude'], min=max(prev_amplitude[k-1]*0.95, prev_amplitude[k]), max=prev_amplitude[k-1]*1.05 and remaining_intensity - 200, vary=True)
        
            # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
            elif k == 3:
                pars[f'v3_amplitude'].set(expr=f'{remaining_intensity} - v2_amplitude', vary=False)
        
            else:
                pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

            pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95, max=prev_sigma[k-1]*1.05)
            pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95, max=prev_gamma[k-1]*1.05)         
            
        mod = voigt1
        for l in range(2, n+1):
            mod += VoigtModel(prefix=f'v{l}_')

        init = mod.eval(pars, x=th[0])
        out = mod.fit(In[0], pars, x=th[0])
        comps = out.eval_components(x=th[0])
        
        # ループ後に prev_center, prev_sigma, prev_gamma を更新 
        
        prev_center = []
        prev_amplitude = []
        prev_sigma = []
        prev_gamma = []
        
        for r in range(1, n+1):
            prev_center.append(float(out.best_values.get(f'v{r}_center')))
            prev_amplitude.append(float(out.best_values.get(f'v{r}_amplitude')))
            prev_sigma.append(float(out.best_values.get(f'v{r}_sigma')))
            prev_gamma.append(float(out.best_values.get(f'v{r}_gamma')))
            Init_pars[f'v{r}_center'] = float(out.best_values.get(f'v{r}_center'))
            Init_pars[f'v{r}_amplitude'] = float(out.best_values.get(f'v{r}_amplitude'))
            Init_pars[f'v{r}_sigma'] = float(out.best_values.get(f'v{r}_sigma'))
            Init_pars[f'v{r}_gamma'] = float(out.best_values.get(f'v{r}_gamma'))

            
        # フィッティング結果の格納
        cur_result = np.empty((1, 1 + n * 3), dtype=object)  # 1行分の結果を格納
        cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
        for m in range(1, n+1):
            cur_result[0][1+(m-1)*3] = out.best_values.get(f'v{m}_center')
            cur_result[0][2+(m-1)*3] = out.best_values.get(f'v{m}_amplitude')
            c = out.best_values.get(f'v{m}_sigma')
            d = out.best_values.get(f'v{m}_gamma')
            cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)   
        
        # 残差の平均を計算
        residual_mean = np.mean(np.abs(out.residual))

        max_attempts = 30  # 最大試行回数
        attempt = 0  # 試行回数カウンター
        
        #残差が大きい場合の処理
        
        while residual_mean >= residual_limit and attempt < max_attempts:
            print(f"Attempt {attempt + 1}: Residual too high ({residual_mean}), adjusting initial parameters and refitting...")
            
            # 初期値をランダムに変化させる
            Init_pars["v2_center"] += random.uniform(-0.001, 0.001)  # 例: ±0.02 変化
            Init_pars["v2_amplitude"] *= random.uniform(0.99, 1.01) 
            Init_pars["v2_sigma"] *= random.uniform(0.98, 1.01)  # 例: 5% 変化
            Init_pars["v2_gamma"] *= random.uniform(0.98, 1.01)
        
            # フィッティング開始
            voigt1 = VoigtModel(prefix='v1_')
            pars = voigt1.guess(In[0], x=th[0])
        
            # 残りのピークの強度合計
            remaining_intensity = total_I - v1_new_amplitude
            
            pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
            pars['v1_amplitude'].set(value=v1_new_amplitude, min=v1_new_amplitude*0.98, max=v1_new_amplitude*1.02)  # 1つ目のピークの強度を固定
            pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97, max=prev_sigma[0]*1.03)
            pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97, max=prev_gamma[0]*1.03)

            # 2つ目以降のピークの設定
            for k in range(2, n+1):
                pars.update(VoigtModel(prefix=f'v{k}_').make_params())

                # th の大小関係を固定
                pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=prev_center[k-1]*0.97 and prev_center[k-2] + 0.05, max=prev_center[k-1]*1.03)  # 前のピークより大きい値にする

                # 2つ目のピークの強度を自由に変化させる
                if k == 2:
                    pars[f'v2_amplitude'].set(value=Init_pars[f'v2_amplitude'], min=max(prev_amplitude[k-1]*0.95, prev_amplitude[k]), max=prev_amplitude[k-1]*1.05 and remaining_intensity - 200, vary=True)
            
                # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
                elif k == 3:
                    pars[f'v3_amplitude'].set(expr=f'{remaining_intensity} - v2_amplitude', vary=False)
            
                else:
                    pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

                pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95, max=prev_sigma[k-1]*1.05)
                pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95, max=prev_gamma[k-1]*1.05)   
        
            mod = voigt1
            for l in range(2, n+1):
                mod += VoigtModel(prefix=f'v{l}_')
        
            init = mod.eval(pars, x=th[0])
            out = mod.fit(In[0], pars, x=th[0])
            comps = out.eval_components(x=th[0])
            
            prev_residual=residual_mean
        
            residual_mean = np.mean(np.abs(out.residual))
            print(f"Residual mean after fitting: {residual_mean}")
        
            attempt += 1  # 試行回数をカウント
            
            if residual_mean < prev_residual:
                
                prev_residual=residual_mean
            
                # ループ後に prev_center, prev_sigma, prev_gamma を更新
                prev_center = []
                prev_amplitude = []
                prev_sigma = []
                prev_gamma = []   
                
                for r in range(1, n+1):
                    """
                    diff_squared_sum_center += (prev_center[r-1] - out.best_values.get(f'v{r}_center'))**2
                    diff_squared_sum_amplitude += (prev_amplitude[r-1] - out.best_values.get(f'v{r}_amplitude'))**2
                    diff_squared_sum_sigma += (prev_sigma[r-1] - out.best_values.get(f'v{r}_sigma'))**2
                    diff_squared_sum_gamma += (prev_gamma[r-1] - out.best_values.get(f'v{r}_gamma'))**2
                    """
                    prev_center.append(float(out.best_values.get(f'v{r}_center')))
                    prev_amplitude.append(float(out.best_values.get(f'v{r}_amplitude')))
                    prev_sigma.append(float(out.best_values.get(f'v{r}_sigma')))
                    prev_gamma.append(float(out.best_values.get(f'v{r}_gamma')))
        
                    Init_pars[f'v{r}_center'] = prev_center[-1]
                    Init_pars[f'v{r}_amplitude'] = prev_amplitude[-1]
                    Init_pars[f'v{r}_sigma'] = prev_sigma[-1]
                    Init_pars[f'v{r}_gamma'] = prev_gamma[-1]
        
        # 最大試行回数に達した場合の処理
        if residual_mean >= residual_limit:
            print(f"Max attempts reached ({max_attempts}). Residual still high ({residual_mean}). Returning to previous step.")
            # 必要なら、エラーハンドリングや別の処理を追加
            #残差を合計に加算
            
        elif residual_mean <residual_limit:
            # フィッティング結果の格納
            cur_result = np.empty((1, 1 + n * 3), dtype=object)  # 1行分の結果を格納
            cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
            for m in range(1, n+1):
                cur_result[0][1+(m-1)*3] = out.best_values.get(f'v{m}_center')
                cur_result[0][2+(m-1)*3] = out.best_values.get(f'v{m}_amplitude')
                c = out.best_values.get(f'v{m}_sigma')
                d = out.best_values.get(f'v{m}_gamma')
                cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)   
            
            #残差を合計に加算
            total_residual += residual_mean
            print(residual_mean)
            
        
        

        #フィッテングの結果描画
        fig, ax = plt.subplots(2,1,dpi=130)
        ax=ax.ravel()
        ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip("bcg.csv")[-4:]))
        ax[0].plot(th[0], out.best_fit, '-', label=f'{v1_new_amplitude}best fit',zorder=10,lw=2)
        ax[1].plot(th[0], In[0], 'C6o',alpha=0.5)
        for p in range(1, n+1):
            ax[1].plot(th[0], comps['v' + str(p) + '_'], 'C'+str(p)+'--', label='component'+str(p))
        ax[0].set(xlabel="2theta",ylabel="Intensity")
        ax[1].set(xlabel="2theta",ylabel="Intensity")
        ax[0].set_xlim(th_min, th_max)
        ax[0].set_ylim(-100, ylim_max)
        ax[0].set_xlim(th_min, th_max)
        ax[1].set_xlim(th_min, th_max)
        ax[1].set_ylim(-100, ylim_max)
        ax[0].legend(loc='best')
        ax[1].legend(loc='best')
        plt.show()
        #フィッテングの結果描画　終わり

        
        # フィッティング結果の格納
        cur_result = np.empty((1, 1 + n * 3), dtype=object)  # 1行分の結果を格納
        cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
        for m in range(1, n+1):
            cur_result[0][1+(m-1)*3] = out.best_values.get(f'v{m}_center')
            cur_result[0][2+(m-1)*3] = out.best_values.get(f'v{m}_amplitude')
            c = out.best_values.get(f'v{m}_sigma')
            d = out.best_values.get(f'v{m}_gamma')
            cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)     
        
        if all_results.size == 0:
            all_results = cur_result  # 初回はそのまま代入
        else:
            all_results = np.vstack([all_results, cur_result])  # 縦方向に追加

        print("fitted:", all_results[-1, 0])
        
    col = ['num', '2th_'+ peaks[0], 'I_'+ peaks[0], 'FWHM_'+ peaks[0], '2th_'+ peaks[1], 'I_'+ peaks[1], 'FWHM_'+ peaks[1], '2th_'+ peaks[2], 'I_'+ peaks[2], 'FWHM_'+ peaks[2]]
    df = pd.DataFrame(all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/
    
    #パラメータの描画
    fig, ax = plt.subplots(3*n,1,dpi=130)
    ax=ax.ravel()

    for i in range(0, n):
        ax[0+i*3].plot(df["num"], df[col[1+i*3]], '.', label=col[1+i*3]+str(v1_new_amplitude)) # https://pythondatascience.plavox.info/pandas/%E8%A1%8C%E3%83%BB%E5%88%97%E3%81%AE%E6%8A%BD%E5%87%BA
        ax[1+i*3].plot(df["num"], df[col[2+i*3]], '.', label=col[2+i*3])
        ax[2+i*3].plot(df["num"], df[col[3+i*3]], '.', label=col[3+i*3]) 

        ax[0+i*3].legend()
        ax[1+i*3].legend()
        ax[2+i*3].legend()
      
    plt.show()

    # すべてのファイルの残差の平均が最小なら更新
    if total_residual < best_total_residual:
        best_total_residual = total_residual
        best_v1_amplitude = v1_new_amplitude
        best_results = all_results  # 最良の結果を保存


#外部ファイルに出力
col = ['num', '2th_'+ peaks[0], 'I_'+ peaks[0], 'FWHM_'+ peaks[0], '2th_'+ peaks[1], 'I_'+ peaks[1], 'FWHM_'+ peaks[1], '2th_'+ peaks[2], 'I_'+ peaks[2], 'FWHM_'+ peaks[2]]
df = pd.DataFrame(best_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/

with pd.ExcelWriter(out_path, engine="openpyxl", mode='a', if_sheet_exists='new') as writer:
    df.to_excel(writer, sheet_name=excel_sheet + "refined", index=False)


#パラメータの描画
fig, ax = plt.subplots(3*n,1,dpi=130)
ax=ax.ravel()

for i in range(0, n):
    ax[0+i*3].plot(df["num"], df[col[1+i*3]], '.', label=col[1+i*3]) # https://pythondatascience.plavox.info/pandas/%E8%A1%8C%E3%83%BB%E5%88%97%E3%81%AE%E6%8A%BD%E5%87%BA
    ax[1+i*3].plot(df["num"], df[col[2+i*3]], '.', label=col[2+i*3])
    ax[2+i*3].plot(df["num"], df[col[3+i*3]], '.', label=col[3+i*3]) 

    ax[0+i*3].legend()
    ax[1+i*3].legend()
    ax[2+i*3].legend()
  
plt.show()

#出力データを格納する変数の定義
all_results = np.empty((1,1+n*3), float) # https://pyming.info/2022/02/10/numpy_empty/
cur_result = np.empty((1,1+n*3), float)

# すべてのファイルで共通のピーク強度を見つけるための変数
best_v1_amplitude = None
best_total_residual = float('inf')
best_results = None