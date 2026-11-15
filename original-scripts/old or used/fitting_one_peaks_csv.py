# -*- coding: utf-8 -*-
"""
Created on Wed Jan 29 11:31:04 2025

@author: harad
"""

# peak fitting するプログラム (ピーク１個)

# Lmfitを仮想環境(今回はfitting1)にpip install する / matplotlib, pandas, openexlはconda install　
#https://qiita.com/mckeeeen/items/d4cbe4a16a102157f40c

#仮想環境(今回はfitting1)でspyderを開く
#https://work-life-enj.com/spyder-virtual-environment/

import matplotlib.pyplot as plt
import numpy as np
import os 
from lmfit.models import VoigtModel
import math
import pandas as pd
import random

peaks=["fcc200", "fcc220", "bcc211", "fcc311"]  #"fcc200", "fcc220", "bcc211", "fcc311"

def perform_fitting(init_params):
    """ 与えられた初期パラメータでフィッティングを実行し、結果を返す """
    voigt1 = VoigtModel(prefix='v1_')
    pars = voigt1.guess(In[0], x=th[0])
    pars['v1_center'].set(value=init_params["v1_center"], min=0)
    pars['v1_amplitude'].set(value=init_params["v1_amplitude"], min=0)
    pars['v1_sigma'].set(value=init_params["v1_sigma"], min=0)
    pars['v1_gamma'].set(value=init_params["v1_gamma"], min=0)

    for k in range(2, n + 1):
        pars.update(VoigtModel(prefix=f'v{k}_').make_params())
        pars[f'v{k}_center'].set(value=init_params[f'v{k}_center'], min=0)
        pars[f'v{k}_amplitude'].set(value=init_params[f'v{k}_amplitude'], min=0)
        pars[f'v{k}_sigma'].set(value=init_params[f'v{k}_sigma'], min=0)
        pars[f'v{k}_gamma'].set(value=init_params[f'v{k}_gamma'], min=0)

    mod = voigt1
    for l in range(2, n + 1):
        mod += VoigtModel(prefix=f'v{l}_')

    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    
    return out

CR="0CR"
C_content="0.5C"
folder_path="F:\\修士データ\\SP8\\diffraction data"

for peak in peaks:

    #入力-----------------------------------------------------------------------------
    # 処理したいファイルの入っているフォルダパス
    in_path = f'{folder_path}\\{C_content}\\{CR}\\bcg_removed2\\'
    #出力するファイルパス
    out_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}output.xlsx'
    #初期値（originでフィッテングした結果）の格納されたファイルパス
    init_path = f'{folder_path}\\{C_content}\\{CR}\\{C_content}{CR}_{peak}_initial.xlsx'
    
    
    #ピークの数
    n = 1   
    residual_limit = 1.5
        
    #--------------------------------------------------------------------------------
    
    #初期値の読み込み
    data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6], skiprows=[0]) # https://note.nkmk.me/python-pandas-read-excel/
    data = data_pd.values # https://note.nkmk.me/python-pandas-numpy-conversion/
    #--------------------------------------------------------------------------------
    
    #初期値の読み込み
    data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6], skiprows=[0]) # https://note.nkmk.me/python-pandas-read-excel/
    data = data_pd.values # https://note.nkmk.me/python-pandas-numpy-conversion/
    
    #初期値
    Init_pars = {}
    Init_pars['num'] = data[0][0]
    Init_pars['v1_center'] = data[0][1]
    Init_pars['v1_amplitude'] = data[0][2]
    Init_pars['v1_sigma'] = data[0][3]/(2*math.sqrt(4*math.log(2, math.e)))
    Init_pars['v1_gamma'] = data[0][4]/2
    FWHM_initial=pd.read_excel(init_path, usecols=[7], skiprows=[0]).values[0][0]
    
    #フィッテングする回折角2thetaの範囲の最小値
    th_min = Init_pars['v1_center']-1.0
    #フィッテングする回折角2thetaの範囲の最大値
    th_max = Init_pars['v1_center']+0.3
    
    #プロットのy軸の最大値
    ylim_max = Init_pars['v1_amplitude']//FWHM_initial
    
    #処理ファイルの名前リストと数
    all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
    cont_all_file = len(all_file)
    
    
    #出力データを格納する変数の定義
    all_results = np.empty((1,1+n*3), float) # https://pyming.info/2022/02/10/numpy_empty/
    cur_result = np.empty((1,1+n*3), float)
    
    
    for i in range(cont_all_file):
        
        best_residual = 10000
        
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
        
        if in_file.size == 0:
            print(f"ファイル {in_file_path} が空です。")
            continue
        
        # 条件に合致するデータの数を確認
        count_th = np.count_nonzero((in_file >= th_min) & (in_file <= th_max), axis=0)[0]
        if count_th == 0:
            print(f"条件に一致するデータがありません。ファイル: {in_file_path}")
            continue
    
        # 回折角 th と強度 In を格納
        th_filtered = [row for row in in_file if (row[0] >= th_min) and (row[0] <= th_max)]
        th = np.array([row[0] for row in th_filtered], dtype=float).reshape(1, -1)
        In = np.array([row[1] for row in th_filtered], dtype=float).reshape(1, -1)
        
        # フィッティング処理
        if th.size == 0 or In.size == 0:
            print(f"フィルタリング結果が空です。ファイル: {in_file_path}")
            continue
        
        #フィッテング開始
        
        # 初期値をランダムに変化させる
        Init_pars["v1_sigma"] *= random.uniform(0.99, 1.01)  # 例: 5% 変化
        Init_pars["v1_gamma"] *= random.uniform(0.99, 1.01)
        
        voigt1 = VoigtModel(prefix='v1_')
        pars = voigt1.guess(In[0], x=th[0])
        pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.95, max=prev_center[0]*1.05)
        pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"])  # 1つ目のピークの強度を固定
        pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.95, max=prev_sigma[0]*1.05)
        pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.95, max=prev_gamma[0]*1.05)
        
        for k in range(2, n+1):
            pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
            pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center'], min=0)
            pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude'], min=0)
            pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
            pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
        
        mod = voigt1
        for l in range(2, n+1):
            mod += VoigtModel(prefix='v' + str(l) + '_')
        
        init = mod.eval(pars, x=th[0])
        out = mod.fit(In[0], pars, x=th[0])
        comps = out.eval_components(x=th[0])
        #フィッテング終わり
        
        residual_mean = np.mean(np.abs(out.residual))
        relative_residual = residual_mean / np.mean(np.abs(In[0]))
        
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
            
            """
            Init_pars[f'v{r}_center'] = float(out.best_values.get(f'v{r}_center'))
            Init_pars[f'v{r}_amplitude'] = float(out.best_values.get(f'v{r}_amplitude'))
            Init_pars[f'v{r}_sigma'] = float(out.best_values.get(f'v{r}_sigma'))
            Init_pars[f'v{r}_gamma'] = float(out.best_values.get(f'v{r}_gamma'))    
            """
        
        #パラメータの出力
        

        # 2回目以降で、もしフィッティングの残差が大きかったら、HCP002のth（ピーク位置）の初期値を調整する

        
        if relative_residual < residual_limit:
            print(relative_residual)
        
        max_attempts = 10  # 最大試行回数
        attempt = 0  # 試行回数カウンター
        
        while relative_residual >= residual_limit and attempt < max_attempts:
            print(f"Attempt {attempt + 1}: Residual too high ({residual_mean}), adjusting initial parameters and refitting...")
            
            # 初期値をランダムに変化させる
            Init_pars["v1_center"] += random.uniform(-0.01, 0.01)  # 例: ±0.02 変化
            Init_pars["v1_sigma"] *= random.uniform(0.97, 1.03)  # 例: 5% 変化
            Init_pars["v1_gamma"] *= random.uniform(0.97, 1.03)
        
            # フィッティング開始
            voigt1 = VoigtModel(prefix='v1_')
            pars = voigt1.guess(In[0], x=th[0])
        
            
            pars = voigt1.guess(In[0], x=th[0])
            pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.95, max=prev_center[0]*1.05)
            pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"])  # 1つ目のピークの強度を固定
            pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.95, max=prev_sigma[0]*1.05)
            pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.95, max=prev_gamma[0]*1.05)
        
            
        
            mod = voigt1
            for l in range(2, n+1):
                mod += VoigtModel(prefix=f'v{l}_')
        
            init = mod.eval(pars, x=th[0])
            out = mod.fit(In[0], pars, x=th[0])
            comps = out.eval_components(x=th[0])
            
        
            residual_mean = np.mean(np.abs(out.residual))
            relative_residual = residual_mean / np.mean(np.abs(In[0]))
            print(f"Residual after fitting: {relative_residual}")
        
            attempt += 1  # 試行回数をカウント
            
            
            if relative_residual < best_residual:
                best_residual = relative_residual
                
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
                        
                    """
                    Init_pars[f'v{r}_center'] = prev_center[-1]
                    Init_pars[f'v{r}_amplitude'] = prev_amplitude[-1]
                    Init_pars[f'v{r}_sigma'] = prev_sigma[-1]
                    Init_pars[f'v{r}_gamma'] = prev_gamma[-1]
                    """
            
        # 最大試行回数に達した場合の処理
        if relative_residual >= residual_limit:
            print(f"Max attempts reached ({max_attempts}). Residual still high ({residual_mean}). Returning to previous step.")
            #フィッテング開始
            
            voigt1 = VoigtModel(prefix='v1_')
            pars = voigt1.guess(In[0], x=th[0])
            pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.95, max=prev_center[0]*1.05)
            pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"])  # 1つ目のピークの強度を固定
            pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.95, max=prev_sigma[0]*1.05)
            pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.95, max=prev_gamma[0]*1.05)
            
            for k in range(2, n+1):
                pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
                pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center'], min=0)
                pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude'], min=0)
                pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
                pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
            
            mod = voigt1
            for l in range(2, n+1):
                mod += VoigtModel(prefix='v' + str(l) + '_')
            
            init = mod.eval(pars, x=th[0])
            out = mod.fit(In[0], pars, x=th[0])
            comps = out.eval_components(x=th[0])
            #フィッテング終わり
            
                                
        #フィッテングの結果描画
        fig, ax = plt.subplots(2,1,dpi=130)
        ax=ax.ravel()
        ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip("bcg.csv")[-4:])+"_"+peak)
        ax[0].plot(th[0], out.best_fit, '-', label='best fit',zorder=10,lw=2)
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
                
        # 初回の処理（all_resultsの初期化）
        if i == 0:
            all_results = cur_result  # 初回はそのまま代入
        else:
            if cur_result.shape[1] == all_results.shape[1]:  # 列数が一致するか確認
                all_results = np.vstack([all_results, cur_result])  # 縦方向に追加

        print("fitted:"+peak, all_results[-1, 0])
     
    
    #外部ファイルに出力
    col = ['num', '2th_'+ peak, 'I_'+ peak, 'FWHM_'+ peak]
    df = pd.DataFrame(all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/
    
    with pd.ExcelWriter(out_path, engine="openpyxl", mode='a', if_sheet_exists='new') as writer:
        df.to_excel(writer, sheet_name=peak, index=False)
    
    
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