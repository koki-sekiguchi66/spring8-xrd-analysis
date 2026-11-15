# -*- coding: utf-8 -*-
"""
Created on Sat May 24 22:34:50 2025

@author: harad
"""

# peak fitting するプログラム

# Lmfit, randomを仮想環境(今回はfitting1)にpip install する / matplotlib, pandas, openpyxlはconda install　
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
from pathlib import Path
from datetime import datetime


"""
フィッティングの前に...
バックグラウンドを処理したファイルをbcg_removedという名前のフォルダに入れる。
フィッティングを行いたいピーク全てについて、originで初期値をフィッティングし、結果を「file_nameの内容」_「ピークの名前(peaksに入れた内容)」_initial.xlsx（ex. 1.0C90CR_fcc111bcc110_initialなど）の形でbcg_removedと同じフォルダ内に入れる。
"""

#入力-----------------------------------------------------------------------------

#処理したいフォルダのアドレス（bcg_removedのあるフォルダパス）
folder_path = Path(r"F:\卒論関連\卒論実験データ\SPring-8\diffracion data\0.5C\LN2")

#アウトプット先のおよび初期値のファイル名
file_name = "0.5CLN2"

residual_limit = 800 #残差の上限（データセットごとに適当な値を決める。）
max_attempts = 5  #残差が大きいときの繰り返しの回数の上限 

#ピークの数
n = 2
#回折角の小さい順のピーク
peaks = ["bct211", "bct112"] #解析したいピーク（重なっている2つ）"fcc111", "bcc110"

excel_sheet=""
for i in range(len(peaks)):
    print(peaks[i],end='')
    excel_sheet+=peaks[i]
#------------------------------

# 処理したいファイルの入っているフォルダパス
in_path = fr'{folder_path}\bcg_removed_mono\\' #最後だけ\\にする 
#出力するファイルパス
out_path = fr'{folder_path}\\{file_name}output.xlsx'
#初期値（originでフィッテングした結果）の格納されたファイルパス
init_path = fr'{folder_path}\\{file_name}_{excel_sheet}_initial.xlsx' 

#--------------------------------------------------

#初期値の読み込み
data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6, 9, 10, 11, 12], skiprows=[0]) # https://note.nkmk.me/python-pandas-read-excel/
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
th_min = Init_pars['v1_center']-0.7
#フィッテングする回折角2thetaの範囲の最大値
th_max = Init_pars['v1_center']+0.7

#プロットのy軸の最大値
ylim_max = Init_pars['v1_amplitude']//FWHM_initial*1.5


#処理ファイルの名前リストと数
all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
cont_all_file = len(all_file)


#出力データを格納する変数の定義
all_results = np.empty((1,1+n*3), float) # https://pyming.info/2022/02/10/numpy_empty/
cur_result = np.empty((1,1+n*3), float)

prev_center = []
prev_amplitude = []
prev_sigma = []
prev_gamma = []


for i in range(0, cont_all_file):
    
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
    
    #処理したいファイルの読み込み
    in_file_path = in_path + all_file[i]
    in_file = np.loadtxt(in_file_path, delimiter=",", dtype = 'float')
        
    # number of theta data 
    count_th = np.count_nonzero((in_file >= th_min) & (in_file <= th_max), axis=0)[0]
    
    #回折角thと強度Inをそれぞれ2次元配列に格納する変数の定義
    th = np.empty((1, count_th), float)
    In = np.empty((1, count_th), float)
    
    #回折角thと強度Inをそれぞれ2次元配列に格納
    u_th = 0
    for j in range(0, len(in_file)):
        if (in_file[j][0] >= th_min) and (in_file[j][0] <= th_max):
            th[0][u_th] = in_file[j][0]
            In[0][u_th] = in_file[j][1] 
            u_th += 1 

    #フィッティング開始    
    
    # 初期値をランダムに変化させる
    Init_pars["v1_amplitude"] *= random.uniform(0.999, 1.001) 
    Init_pars["v1_sigma"] *= random.uniform(0.999, 1.001)  # 例: 5% 変化
    Init_pars["v1_gamma"] *= random.uniform(0.999, 1.001)
    #Init_pars["v2_center"] += random.uniform(-0.0002, 0.0001)  # 例: ±0.02 変化
    #Init_pars["v2_amplitude"] *= random.uniform(0.999, 1.001) 
    #Init_pars["v2_sigma"] *= random.uniform(0.999, 1.002)  # 例: 5% 変化
    #Init_pars["v2_gamma"] *= random.uniform(0.999, 1.002)
    
    voigt1 = VoigtModel(prefix='v1_')
    pars = voigt1.guess(In[0], x=th[0])
    
    pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
    pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=prev_amplitude[0]*0.9, max=prev_amplitude[0]*1.2)  # 1つ目のピークの強度を固定
    pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97-0.00001, max=prev_sigma[0]*1.03)
    pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97-0.00001, max=prev_gamma[0]*1.03)

    # 2つ目以降のピークの設定
    for k in range(2, n+1):
        pars.update(VoigtModel(prefix=f'v{k}_').make_params())

        # th の大小関係を固定
        pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=max(prev_center[k-1]*0.997,prev_center[k-2] + 0.13), max=prev_center[k-1]*1.002)  # 前のピークより大きい値にする

        # 2つ目のピークの強度を自由に変化させる
        if k == 2:
            pars['v2_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=max(prev_amplitude[k-1]*0.97-10, 0), max=prev_amplitude[k-1]*1.01+20)  # 前のピークより大きい値にする
    
        # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
        elif k == 3:
            pars['v3_amplitude'].set(value=Init_pars['v3_amplitude'], min=prev_amplitude[k-1]*0.95, max=prev_amplitude[k-1]*1.05, vary=True)
    
        else:
            pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

        pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95-0.00001, max=prev_sigma[k-1]*1.005)
        pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95-0.00001, max=prev_gamma[k-1]*1.005)
        
    mod = voigt1
    for l in range(2, n+1):
        mod += VoigtModel(prefix=f'v{l}_')

    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    
    # 残差の平均を計算
    residual_mean = np.mean(np.abs(out.residual))
    
    if residual_mean < residual_limit:
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

        
    


    
    attempt = 0  # 試行回数カウンター
    
    #残差が大きい場合の処理
    
    while residual_mean >= residual_limit and attempt < max_attempts:
        print(f"Attempt {attempt + 1}: Residual too high ({residual_mean}), adjusting initial parameters and refitting...")
        
        # 初期値をランダムに変化させる
        Init_pars["v1_sigma"] *= random.uniform(0.99, 1.01)  # 例: 5% 変化
        Init_pars["v1_gamma"] *= random.uniform(0.99, 1.01)
        Init_pars["v2_center"] += random.uniform(-0.00, 0.005)  # 例: ±0.02 変化
        Init_pars["v2_amplitude"] *= random.uniform(0.99, 1.02) 
        Init_pars["v2_sigma"] *= random.uniform(0.99, 1.02)  # 例: 5% 変化
        Init_pars["v2_gamma"] *= random.uniform(0.99, 1.02)
    
        # フィッティング開始
        voigt1 = VoigtModel(prefix='v1_')
        pars = voigt1.guess(In[0], x=th[0])
        
        pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
        pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=prev_amplitude[0]*0.9, max=prev_amplitude[0]*2)  # 1つ目のピークの強度を固定
        pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97-0.00001, max=prev_sigma[0]*1.03)
        pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97-0.00001, max=prev_gamma[0]*1.03)

        # 2つ目以降のピークの設定
        for k in range(2, n+1):
            pars.update(VoigtModel(prefix=f'v{k}_').make_params())

            # th の大小関係を固定
            pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=max(prev_center[k-1]*0.997,prev_center[k-2] + 0.13), max=prev_center[k-1]*1.002)  # 前のピークより大きい値にする

            # 2つ目のピークの強度を自由に変化させる
            if k == 2:
                pars['v2_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=max(prev_amplitude[k-1]*0.97-10, 0), max=prev_amplitude[k-1]*1.01+20)  # 前のピークより大きい値にする
        
            # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
            elif k == 3:
                pars['v3_amplitude'].set(value=Init_pars['v3_amplitude'], min=prev_amplitude[k-1]*0.95, max=prev_amplitude[k-1]*1.05, vary=True)
        
            else:
                pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

            pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95-0.00001, max=prev_sigma[k-1]*1.005)
            pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95-0.00001, max=prev_gamma[k-1]*1.005)
    
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
        
        if residual_mean < residual_limit:
            
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
        # フィッティング開始
        voigt1 = VoigtModel(prefix='v1_')
        pars = voigt1.guess(In[0], x=th[0])
        
        pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.97, max=prev_center[0]*1.03)
        pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=prev_amplitude[0]*0.9, max=prev_amplitude[0]*1.1)  # 1つ目のピークの強度を固定
        pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.97-0.00001, max=prev_sigma[0]*1.03)
        pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.97-0.00001, max=prev_gamma[0]*1.03)

        # 2つ目以降のピークの設定
        for k in range(2, n+1):
            pars.update(VoigtModel(prefix=f'v{k}_').make_params())

            # th の大小関係を固定
            pars[f'v{k}_center'].set(value=Init_pars[f'v{k}_center'], min=max(prev_center[k-1]*0.997,prev_center[k-2] + 0.13), max=prev_center[k-1]*1.002)  # 前のピークより大きい値にする

            # 2つ目のピークの強度を自由に変化させる
            if k == 2:
                pars['v2_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=max(prev_amplitude[k-1]*0.97-10, 0), max=prev_amplitude[k-1]*1.01+20)  # 前のピークより大きい値にする
        
            # 3つ目のピークの強度を「remaining_intensity - v2_amplitude」に固定
            elif k == 3:
                pars['v3_amplitude'].set(value=Init_pars['v3_amplitude'], min=prev_amplitude[k-1]*0.95, max=prev_amplitude[k-1]*1.05, vary=True)
        
            else:
                pars[f'v{k}_amplitude'].set(value=Init_pars[f'v{k}_amplitude'], min=0, vary=True)  # その他のピークは自由

            pars[f'v{k}_sigma'].set(value=Init_pars[f'v{k}_sigma'], min=prev_sigma[k-1]*0.95-0.00001, max=prev_sigma[k-1]*1.005)
            pars[f'v{k}_gamma'].set(value=Init_pars[f'v{k}_gamma'], min=prev_gamma[k-1]*0.95-0.00001, max=prev_gamma[k-1]*1.005)   
    
        mod = voigt1
        for l in range(2, n+1):
            mod += VoigtModel(prefix=f'v{l}_')
    
        init = mod.eval(pars, x=th[0])
        out = mod.fit(In[0], pars, x=th[0])
        comps = out.eval_components(x=th[0])
        print(f"Max attempts reached ({max_attempts}). Residual still high ({residual_mean}). Returning to previous step.")
        # 必要なら、エラーハンドリングや別の処理を追加
        #残差を合計に加算
        
    elif residual_mean < residual_limit:
        # フィッティング結果の格納
        cur_result = np.empty((1, 1 + n * 3), dtype=object)  # 1行分の結果を格納
        cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
        for m in range(1, n+1):
            cur_result[0][1+(m-1)*3] = out.best_values.get(f'v{m}_center')
            cur_result[0][2+(m-1)*3] = out.best_values.get(f'v{m}_amplitude')
            c = out.best_values.get(f'v{m}_sigma')
            d = out.best_values.get(f'v{m}_gamma')
            #print(f"Iteration {i}, Peak {m}: sigma={c}, gamma={d}, FWHM={1.0692*d + math.sqrt(0.8664*d**2 + 5.545083*c**2)}")
            cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)   
        
        print(residual_mean)   
    

    #フィッテングの結果描画
    fig, ax = plt.subplots(2,1,dpi=130)
    ax=ax.ravel()
    ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip("bcg.csv")[-4:]))
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
    ax[1].set_ylim(-100, ylim_max/10)
    ax[0].legend(loc='best')
    ax[1].legend(loc='best')
    plt.show()
    #フィッテングの結果描画　終わり
 
    #2回目以降で、フィッテングがうまくいっていた場合、それまでの結果に追加
    if i == 0:
        all_results[0][0] = all_file[i].rstrip("bcg.csv")[-4:]
        for a in range(1, n+1):
            all_results[0][1+(a-1)*3] = out.best_values.get('v' + str(a) + '_'+'center')
            all_results[0][2+(a-1)*3] = out.best_values.get('v' + str(a) + '_'+'amplitude')
            c = out.best_values.get('v' + str(a) + '_'+'sigma')
            d = out.best_values.get('v' + str(a) + '_'+'gamma')
        all_results[0][3+(a-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)
        print("fitted:", Init_pars['num'])
    
    else:
        cur_result[0][0] = all_file[i].rstrip("bcg.csv")[-4:]
        for m in range(1, n+1):
            cur_result[0][1+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'center')
            cur_result[0][2+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'amplitude')
            c = out.best_values.get('v' + str(m) + '_'+'sigma')
            d = out.best_values.get('v' + str(m) + '_'+'gamma')
            cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)
    all_results = np.append(all_results, cur_result, axis=0) # https://note.nkmk.me/python-pandas-to-excel/
    print("fitted:", all_results[i][0])
               


#外部ファイルに出力
col = ['num', '2th_'+ peaks[0], 'I_'+ peaks[0], 'FWHM_'+ peaks[0], '2th_'+ peaks[1], 'I_'+ peaks[1], 'FWHM_'+ peaks[1]]
df = pd.DataFrame(all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/

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


try:
    # 保存先フォルダが存在しない場合に備え、作成しておく
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 既存ファイルへ追記（モード: 'a'）
    with pd.ExcelWriter(out_path, engine="openpyxl", mode='a', if_sheet_exists='new') as writer:
        df.to_excel(writer, sheet_name=excel_sheet, index=False)

except FileNotFoundError as e:
    print(f"ファイルまたはディレクトリが存在しません：{e}")
    
    # 保存先ディレクトリを再確認・作成
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 新しいファイルとして保存
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=excel_sheet, index=False)

    print(f"新しいファイル {out_path} に保存しました。")

except PermissionError as e:
    print(f"アクセス権限エラー：{e}")

    # 新しいファイル名を作成（日時付き）
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    fallback_path = os.path.splitext(out_path)[0] + f'_fallback_{now}.xlsx'

    print(f"代替として新しいファイルに保存します: {fallback_path}")

    # 保存先ディレクトリを再確認・作成
    os.makedirs(os.path.dirname(fallback_path), exist_ok=True)

    # 新しいファイルに保存
    with pd.ExcelWriter(fallback_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=excel_sheet, index=False)

    print("保存完了")


