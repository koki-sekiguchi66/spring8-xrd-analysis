# -*- coding: utf-8 -*-
"""
Created on Wed Jul 16 11:24:08 2025

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
from lmfit.models import VoigtModel, ConstantModel 
import math
import pandas as pd
import random
from pathlib import Path
from datetime import datetime

peaks=[ "bcc211", "fcc311"]  #解析したいピークを入力（1度以上離れた単一のピークのみ解析可能）"fcc200", "fcc220", "bcc211", "fcc311"

n = 1

CR="50CR"
C_content="0.5C"
folder_path = Path(r"F:\修士データ\SP8\diffraction data\202507101\0.5C50CR")

max_attempts = 30



def fit_one_file(i, sum_residual=True, plot=True, save_results=True):
    global relative_residual, prev_center, prev_amplitude, prev_sigma, prev_gamma, Init_pars, all_results, total_residual, prev_integral, In, th, current_integral, intensity_scale_factor, residual_mean, prev_residual
    
    prev_residual = 10000

    """    
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
            
    print(prev_center)
    """
            
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
    
    #積分強度に基づくスケールファクターを計算
    current_integral = np.trapz(In[0], th[0]) # 現在のデータの積分強度を計算
    
    if i > 0 and prev_integral > 0:
        # 前のファイルの積分強度に対する比率でスケール因子を決定
        intensity_scale_factor = current_integral / prev_integral
    else:
        # 最初のファイルの場合、スケールは1.0
        intensity_scale_factor = 1.0
    
    
    if i == 0:#１つめだけ初期値を修正
        
            
        # 初期値をランダムに変化させる
        for p in range(1,n+1):
            Init_pars[f"v{p}_center"] += random.uniform(-0.001, 0.001)  # 例: ±0.02 変化
            Init_pars[f"v{p}_amplitude"] *= random.uniform(0.97, 1.03) 
            Init_pars[f"v{p}_sigma"] *= random.uniform(0.99, 1.01)  # 例: 5% 変化
            Init_pars[f"v{p}_gamma"] *= random.uniform(0.99, 1.01)
    
        perform_fitting()
    
    
    # 初期値をランダムに変化させる
    for p in range(1,n+1):
        Init_pars[f"v{p}_center"] += random.uniform(-0.0001, 0.0001)  # 例: ±0.02 変化
        Init_pars[f"v{p}_amplitude"] *= random.uniform(0.999, 1.001) 
        Init_pars[f"v{p}_sigma"] *= random.uniform(0.9, 1.1)  # 例: 5% 変化
        Init_pars[f"v{p}_gamma"] *= random.uniform(0.9, 1.1)    
    
    #フィッティング開始    

    perform_fitting()


    attempt = 0  # 試行回数カウンター
    
    #残差が大きい場合の処理
    
    while relative_residual >= residual_limit and attempt < max_attempts:
        print(f"Attempt {attempt + 1}: Residual too high ({relative_residual}), adjusting initial parameters and refitting...")
        
        # 初期値をランダムに変化させる
        for p in range(1,n+1):
            Init_pars[f"v{p}_center"] += random.uniform(-0.001, 0.001)  # 例: ±0.02 変化
            Init_pars[f"v{p}_amplitude"] *= random.uniform(0.97, 1.03) 
            Init_pars[f"v{p}_sigma"] *= random.uniform(0.98, 1.02)  # 例: 5% 変化
            Init_pars[f"v{p}_gamma"] *= random.uniform(0.98, 1.02)
    
        perform_fitting()
        
        prev_residual=relative_residual
        
        print(f"relative_residual after fitting: {relative_residual}")
    
        attempt += 1  # 試行回数をカウント
        
        if relative_residual < prev_residual:
            
            
            prev_residual=relative_residual
            
            """
            # ループ後に prev_center, prev_sigma, prev_gamma を更新
            prev_center = []
            prev_amplitude = []
            prev_sigma = []
            prev_gamma = []   
            """
            
            for r in range(1, n+1):
                Init_pars[f'v{r}_center'] = out.best_values.get(f'v{r}_center')
                Init_pars[f'v{r}_amplitude'] = out.best_values.get(f'v{r}_amplitude')
                Init_pars[f'v{r}_sigma'] = out.best_values.get(f'v{r}_sigma')
                Init_pars[f'v{r}_gamma'] = out.best_values.get(f'v{r}_gamma')    
                """                    
                prev_center.append(float(out.best_values.get(f'v{r}_center')))
                prev_amplitude.append(float(out.best_values.get(f'v{r}_amplitude')))
                prev_sigma.append(float(out.best_values.get(f'v{r}_sigma')))
                prev_gamma.append(float(out.best_values.get(f'v{r}_gamma')))
    
                Init_pars[f'v{r}_center'] = prev_center[-1]
                Init_pars[f'v{r}_amplitude'] = prev_amplitude[-1]
                Init_pars[f'v{r}_sigma'] = prev_sigma[-1]
                Init_pars[f'v{r}_gamma'] = prev_gamma[-1]
                """            
    
    # 最大試行回数に達した場合の処理
    if relative_residual >= residual_limit:
        print(f"Max attempts reached ({max_attempts}). Residual still high ({residual_mean}). Returning to previous step.")
        
        perform_fitting()
       
    if relative_residual < prev_residual:
        
        prev_residual=relative_residual
    
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

            Init_pars[f'v{r}_center'] = prev_center[-1]
            Init_pars[f'v{r}_amplitude'] = prev_amplitude[-1]
            Init_pars[f'v{r}_sigma'] = prev_sigma[-1]
            Init_pars[f'v{r}_gamma'] = prev_gamma[-1] 
       
        
    if sum_residual:
        #残差を合計に加算
        total_residual += residual_mean
        print(residual_mean)
        """
        diff_squared_sum_center += (prev_center[r-1] - out.best_values.get(f'v{r}_center'))**2
        diff_squared_sum_amplitude += (prev_amplitude[r-1] - out.best_values.get(f'v{r}_amplitude'))**2
        diff_squared_sum_sigma += (prev_sigma[r-1] - out.best_values.get(f'v{r}_sigma'))**2
        diff_squared_sum_gamma += (prev_gamma[r-1] - out.best_values.get(f'v{r}_gamma'))**2
        """
        
    if plot:
        # --- フィッティングの結果描画 ---
        
        fig, ax = plt.subplots(2, 1, dpi=100, figsize=(8, 6))
        
        # 1. 全体フィットのプロット (上段 ax[0])
        # ---------------------------------
        base_name = os.path.splitext(all_file[i])[0]
        label_name = str(all_file[i].rstrip("bcg.csv")[-4:])
        
        ax[0].plot(th[0], In[0], 'o', label=label_name, markersize=3) # <-- 変更: データ点のサイズを小さく
        ax[0].plot(th[0], out.best_fit, '-', label=f'Best Fit', zorder=10, lw=2, color='C1')
        ax[0].set_title('Overall Fit Result', fontsize=14)
        ax[0].set_xlabel("2theta (deg.)")
        ax[0].set_ylabel("Intensity (a.u.)")
        ax[0].set_xlim(th_min, th_max)
        ax[0].set_ylim(-100, ylim_max)
        ax[0].legend(loc='best')
        ax[0].grid(linestyle='--', alpha=0.6)
        
        # 2. 成分分離のプロット (下段 ax[1])
        # ---------------------------------
        ax[1].plot(th[0], In[0], 'o', color='gray', alpha=0.5, label='Original Data', markersize=3) # <-- 変更: データ点のサイズを小さく
        for p in range(1, n + 1):
            color_index = (p - 1) % 10
            ax[1].plot(th[0], comps[f'v{p}_'], '-', label=f'Component {p}', color=f'C{color_index}') # <-- 変更: 破線 '--' から実線 '-' へ
        
        ax[1].set_title('Component Separation', fontsize=14)
        ax[1].set_xlabel("2theta (deg.)")
        ax[1].set_ylabel("Intensity (a.u.)")
        ax[1].set_xlim(th_min, th_max)
        ax[1].set_ylim(-100, ylim_max)
        ax[1].legend(loc='best')
        ax[1].grid(linestyle='--', alpha=0.6)
        
        # 3. 描画と後処理
        # ---------------------------------
        plt.tight_layout()
        plt.show()
        plt.close(fig)
        
        # --- フィッティングの結果描画 終わり ---

    if save_results:
        # フィッティング結果の格納
        cur_result = np.empty((1, 1 + n * 5), dtype=object)  # 1行分の結果を格納
        cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
        for m in range(1, n+1):
            cur_result[0][1+(m-1)*5] = out.best_values.get(f'v{m}_center')
            cur_result[0][2+(m-1)*5] = out.best_values.get(f'v{m}_amplitude')
            c = out.best_values.get(f'v{m}_sigma')*2*math.sqrt(4*math.log(2, math.e))
            d = out.best_values.get(f'v{m}_gamma')*2
            cur_result[0][3+(m-1)*5] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)   
            cur_result[0][4+(m-1)*5] = c
            cur_result[0][5+(m-1)*5] = d
        
        if all_results.shape[0] == 0:
            all_results = cur_result
        else:
            all_results = np.vstack([all_results, cur_result])

def perform_fitting():
    global relative_residual, In,th, comps, prev_center, intensity_scale_factor, prev_amplitude, prev_sigma, prev_gamma, Init_pars, all_results, total_residual, prev_integral, current_integral, out, Init_pars, prev_residual, residual_mean
    
    # 1. ピークモデルとバックグラウンドモデルを作成
    peak_model = VoigtModel(prefix='v1_')
    background_model = ConstantModel(prefix='bkg_')
    
    # 2. 2つのモデルを足し合わせて、全体のモデルを作成
    mod = peak_model + background_model
    
    # --- ▼▼▼ ここからが修正部分 ▼▼▼ ---
    
    # 3A. ピークモデルのパラメータだけを guess する
    pars = peak_model.guess(In[0], x=th[0])
    
    # 3B. バックグラウンドモデルのパラメータを作成し、追加する
    pars.update(background_model.make_params())
    
    # 3C. (推奨) バックグラウンドの初期値を設定する
    #      データの最初と最後の10点の平均値などを初期値にすると安定しやすい
    background_guess = np.mean(np.concatenate((In[0][:10], In[0][-10:])))
    pars['bkg_c'].set(value=background_guess, min=0)
    
    # --- ▲▲▲ ここまでが修正部分 ▲▲▲ ---
    
    # 4. 以前と同様に、各パラメータの初期値や範囲を具体的に設定
    # <<< 変更点: スケール因子を使って初期値を設定
    scaled_amplitude_guess = [amp * intensity_scale_factor for amp in prev_amplitude]
    
    # <<< 変更点: value にスケーリングした値を設定
    pars['v1_center'].set(value=Init_pars["v1_center"], min=prev_center[0]*0.98, max=prev_center[0]*1.02)
    pars['v1_amplitude'].set(value=scaled_amplitude_guess[0], min = scaled_amplitude_guess[0]*0.9, max = scaled_amplitude_guess[0]*1.1)
    pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.8, max=prev_sigma[0]*1.2+1e-7)
    pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.8, max=prev_gamma[0]*1.2+1e-7)
    
    
    # 5. フィッティングを実行
    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    
    residual_mean = np.mean(np.abs(out.residual))
    relative_residual = residual_mean / np.mean(np.abs(In[0]))

    
    # <<< 変更点: 次のサイクルのために積分強度を保存
    prev_integral = current_integral


for peak in peaks:

    #入力-----------------------------------------------------------------------------
    # 処理したいファイルの入っているフォルダパス
    in_path = fr'{folder_path}\bcg_removed_mono\\' #最後だけ\\にする 
    #出力するファイルパス
    out_path = fr'{folder_path}\\{C_content}{CR}output.xlsx'
    #初期値（originでフィッテングした結果）の格納されたファイルパス
    init_path = fr'{folder_path}\\{C_content}{CR}_{peak}_initial.xlsx'
    
    
    #ピークの数
    n = 1   
    residual_limit = 0.05
        
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
    th_min = Init_pars['v1_center']-0.5
    #フィッテングする回折角2thetaの範囲の最大値
    th_max = Init_pars['v1_center']+0.7
    
    #プロットのy軸の最大値
    ylim_max = Init_pars['v1_amplitude']//FWHM_initial+100
    
    #処理ファイルの名前リストと数
    all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
    cont_all_file = len(all_file)
    
    
    #出力データを格納する変数の定義
    all_results = np.empty((1,1+n*5), float) # https://pyming.info/2022/02/10/numpy_empty/
    cur_result = np.empty((1,1+n*5), float)
    
    prev_integral = 0.0  # <<< 変更点: 前のファイルの積分強度を保持する変数を追加
    
    #初期値が何番目かを判別しtarget_indexに記憶
    target_num = int(Init_pars["num"])  # ← 167.0 → 167 に変換
    target_str = str(target_num)        # ← "167"

    all_file.sort()  # ファイルが番号順になっていなければ、必要に応じて並べ替える

    # ファイル名に target_str を含む最初のファイルのインデックスを取得
    target_index = -1
    for idx, fname in enumerate(all_file):
        if target_str in fname:
            target_index = idx
            break

    if target_index == -1:
        print(f"指定された番号 {target_str} を含むファイルが見つかりませんでした。")

    for i in reversed(range(0, target_index+1)):
        
        residual_limit = 1.5    
  
        if i > 5:
            residual_limit = 0.8
    
        best_residual = 10000
        
        # 初期値をリストに追加
        if i == target_index:
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
        
        fit_one_file(i, sum_residual=False, plot=True, save_results=True)
        
        
    for i in range(target_index, cont_all_file):
        best_residual = 10000
        
        # 初期値をリストに追加
        if i == target_index:
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
        
        fit_one_file(i, sum_residual=False, plot=True, save_results=True)
    
    # まず、先頭の 'num' だけでリストを初期化
    col = ['num']

    col.extend([f'2th_{peak}', f'I_{peak}', f'FWHM_{peak}', f'wG_{peak}', f'wL_{peak}'])

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
            df.to_excel(writer, sheet_name=peak, index=False)
    
    except FileNotFoundError as e:
        print(f"ファイルまたはディレクトリが存在しません：{e}")
        
        # 保存先ディレクトリを再確認・作成
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
        # 新しいファイルとして保存
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=peak, index=False)
    
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
            df.to_excel(writer, sheet_name=peak, index=False)
    
        print("保存完了")