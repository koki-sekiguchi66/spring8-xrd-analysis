# -*- coding: utf-8 -*-
"""
Created on Fri Oct 10 10:30:44 2025

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
import traceback

peaks=["fcc200", "fcc220", "bcc211", "fcc311"]  #解析したいピークを入力（1度以上離れた単一のピークのみ解析可能）"fcc200", "fcc220", "bcc211", "fcc311"

n = 1

CR="93CR"
C_content="0.6C"
folder_path = Path(r"F:\修士データ\SP8\diffraction data\20251003\0.6C93CR")

max_attempts = 30





def fit_one_file(i, sum_residual=True, plot=True, save_results=True):
    global relative_residual, prev_center, prev_amplitude, prev_sigma, prev_gamma, Init_pars, all_results, total_residual, prev_integral, In, th, current_integral, intensity_scale_factor, residual_mean, prev_residual, results_list
    
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
    th = np.zeros((1, count_th), float)
    In = np.zeros((1, count_th), float)

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
        Init_pars[f"v{p}_sigma"] *= random.uniform(0.95, 1.05)  # 例: 5% 変化
        Init_pars[f"v{p}_gamma"] *= random.uniform(0.95, 1.05)    
    
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
        # フィッティング結果を格納
        cur_result = np.zeros((1, 1 + n * 5), dtype=object)  # 1行分の結果を格納
        cur_result[0][0] = int(all_file[i].removesuffix("bcg.csv")[-4:])
        for m in range(1, n + 1):
            cur_result[0][1 + (m - 1) * 5] = out.best_values.get(f'v{m}_center')
            cur_result[0][2 + (m - 1) * 5] = out.best_values.get(f'v{m}_amplitude')
            c = out.best_values.get(f'v{m}_sigma') * 2 * math.sqrt(4 * math.log(2, math.e))
            d = out.best_values.get(f'v{m}_gamma') * 2
            cur_result[0][3 + (m - 1) * 5] = 1.0692 * d + math.sqrt(0.8664 * d**2 + 5.545083 * c**2)
            cur_result[0][4 + (m - 1) * 5] = c
            cur_result[0][5 + (m - 1) * 5] = d
        
        # リストに行データを追加
        results_list.append(cur_result[0])

def perform_fitting():
    global relative_residual, In,th, comps, prev_center, intensity_scale_factor, prev_amplitude, prev_sigma, prev_gamma, Init_pars, all_results, total_residual, prev_integral, current_integral, out, Init_pars, prev_residual, residual_mean, results_list
    
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
    pars['v1_amplitude'].set(value=scaled_amplitude_guess[0], min = scaled_amplitude_guess[0]*0.9-5, max = scaled_amplitude_guess[0]*1.1+5)
    pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=prev_sigma[0]*0.95, max=prev_sigma[0]*1.05+1e-7)
    pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=prev_gamma[0]*0.95, max=prev_gamma[0]*1.05+1e-7)
    
    
    # 5. フィッティングを実行
    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    
    residual_mean = np.mean(out.residual**2)**0.5
    relative_residual = residual_mean / np.mean(np.abs(In[0]))

    
    # <<< 変更点: 次のサイクルのために積分強度を保存
    prev_integral = current_integral

# 1. パラメータ設定
excel_path = Path(fr'{folder_path}\\{C_content}{CR}_initial.xlsx')
sub_header_marker = 'y0'

# --- 処理の本体 ---
try:
    temp_df = pd.read_excel(excel_path, header=None, engine='openpyxl')
    temp_df_str = temp_df.astype(str)
    sub_header_indices = temp_df_str[temp_df_str.apply(lambda col: col.str.contains(sub_header_marker, na=False)).any(axis=1)].index
    if len(sub_header_indices) == 0:
        raise IndexError(f"ヘッダーの目印 '{sub_header_marker}' がファイルに見つかりませんでした。")

    all_peak_data = {}

    for i, sub_header_idx in enumerate(sub_header_indices):
        main_header_idx = sub_header_idx - 1
        start_row = sub_header_idx + 1
        end_row = sub_header_indices[i+1] if i + 1 < len(sub_header_indices) else len(temp_df)

        main_header = temp_df.iloc[main_header_idx].ffill()
        sub_header = temp_df.iloc[sub_header_idx]
        data_block = temp_df.iloc[start_row:end_row]

        multi_index = pd.MultiIndex.from_arrays([main_header, sub_header])
        block_df = pd.DataFrame(data_block.values, columns=multi_index)
        block_df = block_df.dropna(axis=1, how='all')

        # ステップ⑥: 'No'列を特定し、各ピークのデータフレームに追加する
        
        # 'No'列を特定してSeriesとして抽出（通常は最初の列にあると想定）
        no_col_series = None
        if pd.isna(block_df.columns[0][0]) and block_df.columns[0][1].strip() == 'No':
            no_col_series = block_df.iloc[:, 0]

        # ブロック内の各ピークを処理
        for peak_name in block_df.columns.get_level_values(0).unique():
            # 'No'列のグループ（最上位ヘッダーがNaN）はスキップ
            if pd.notna(peak_name):
                # ピーク名に対応するデータフレームを抽出
                peak_df = block_df[peak_name].copy()
                
                # 'No'列が存在すれば、そのピークのデータフレームの先頭に追加
                if no_col_series is not None:
                    peak_df.insert(0, 'No', no_col_series.values)
                
                # 辞書に格納
                if peak_name not in all_peak_data:
                    all_peak_data[peak_name] = peak_df.dropna(axis=1, how='all')


# exceptブロックを以下のように変更
except Exception as e:
    print("--- 根本原因のエラー ---")
    # 詳細なエラー情報を表示
    traceback.print_exc()
    print("----------------------")
    #sys.exit()

# --- 結果の表示 ---
print("✅ ファイルから以下のキーのデータを読み込みました:")
print(list(all_peak_data.keys()))
print("-" * 30)

# 例として 'bcc211' のデータを表示

for peak in peaks:

    #入力-----------------------------------------------------------------------------
    # 処理したいファイルの入っているフォルダパス
    in_path = fr'{folder_path}\bcg_removed_mono\\' #最後だけ\\にする 
    #出力するファイルパス
    out_path = fr'{folder_path}\\{C_content}{CR}output.xlsx'
    #初期値（originでフィッテングした結果）の格納されたファイルパス
    init_path = fr'{folder_path}\\{C_content}{CR}_initial.xlsx'
    
    
    #ピークの数
    n = 1   
    residual_limit = 0.5
    
    results_list = []
    
    #--------------------------------------------------------------------------------
    
    #初期値の読み込み
    if peak in all_peak_data:
        target_data = all_peak_data[peak].dropna(how='all').reset_index(drop=True)
        
        print(f"キー '{peak}' のデータ ('No'列が追加されていることを確認):")
        print(target_data)
    
        if not target_data.empty:
            first_row_values = target_data.iloc[0]
            no_value = first_row_values['No']
            xc_value = first_row_values['xc']
            print(f"\n-> '{peak}' の 'No' の値: {no_value}")
            print(f"-> '{peak}' の 'xc' の値: {xc_value}")
    
        
            #初期値
            Init_pars = {}
            Init_pars['num'] = float(first_row_values['No'])
            Init_pars['v1_center'] = float(first_row_values['xc'])
            Init_pars['v1_amplitude'] = float(first_row_values['A'])
            Init_pars['v1_sigma'] = float(first_row_values['wG'])/(2*math.sqrt(4*math.log(2, math.e)))
            Init_pars['v1_gamma'] = float(first_row_values['wL'])/2

            
            print(Init_pars)
        
        else:
            print(f"エラー: 指定されたキー '{peak}' はどのブロックにも見つかりませんでした。")
    
    #フィッテングする回折角2thetaの範囲の最小値
    th_min = Init_pars['v1_center']-0.7
    #フィッテングする回折角2thetaの範囲の最大値
    th_max = Init_pars['v1_center']+0.5
    
    #プロットのy軸の最大値
    ylim_max = Init_pars['v1_amplitude']//Init_pars['v1_gamma']+100
    
    #処理ファイルの名前リストと数
    all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
    cont_all_file = len(all_file)
        
    
    #出力データを格納する変数の定義
    all_results = np.zeros((1,1+n*5), float) # https://pyming.info/2022/02/10/numpy_empty/
    cur_result = np.zeros((1,1+n*5), float)
    
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
               

     
    for i in range(target_index+1, cont_all_file):
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
        
        
    # ループ終了後、リストからNumPy配列に変換
    all_results = np.array(results_list)
    
    #1番左の列 ([:, 0]) を基準に、降順でソートするためのインデックスを取得
    sorted_indices = np.argsort(all_results[:, 0])
    
    #取得したインデックスの順に配列の行を並び替える
    sorted_all_results = all_results[sorted_indices]
    
    # まず、先頭の 'num' だけでリストを初期化
    col = ['num']

    col.extend([f'2th_{peak}', f'I_{peak}', f'FWHM_{peak}', f'wG_{peak}', f'wL_{peak}'])

    df = pd.DataFrame(sorted_all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/ 
        
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