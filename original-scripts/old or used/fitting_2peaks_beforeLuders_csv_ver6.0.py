# -*- coding: utf-8 -*-
"""
Created on Mon Oct 27 11:05:02 2025

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
from datetime import datetime
from pathlib import Path
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl import load_workbook
import copy

#入力-----------------------------------------------------------------------------

#処理したいフォルダのアドレス（bcg_removedのあるフォルダパス）
folder_path = Path(r"H:\diffraction data\0.8C_bests\75CR")
specimen_name = "0.8C75CR"

DIMT_onset_num = 0 #マルテンサイト変態が開始するファイル番号

residual_limit = 550
max_attempts = 10  # 最大試行回数

#回折角の小さい順のピーク
peaks = ["fcc111", "bcc110"] # "fcc220", "bcc211", "fcc311", "fcc222", "bcc220", "fcc111", "bcc110", "fcc200"

#ピークの数
n = len(peaks)

excel_sheet=""
for i in range(len(peaks)):
    print(peaks[i], end='')
    excel_sheet+=peaks[i]
    
# 処理したいファイルの入っているフォルダパス
in_path = f'{folder_path}\\bcg_removed_arpls\\'
#出力するファイルパス
out_path = f'{folder_path}\\{specimen_name}output.xlsx'
#初期値（originでフィッテングした結果）の格納されたファイルパス
#init_path = f'{folder_path}\\{specimen_name}_{excel_sheet}_initial.xlsx'


# パラメータ名のリストを定義
param_names = ['center', 'amplitude', 'sigma', 'gamma']


#3要素タプルリスト（[(a, b, 1)]の形）で入力
update_list = [
    ('v2', 'amplitude_min_factor', 0.995),
    ('v2', 'center_max_offset', +0.0005)
]

default_fit_limits = {
    'v1': {
        # Center
        'center_min_offset': -0.01,
        'center_max_offset': 0.01,
        
        # Amplitude
        'amplitude_min_factor': 0.9,
        'amplitude_max_factor': 1.1,
        'amplitude_max_offset': 10,
        
        # Sigma
        'sigma_min_factor': 0.99,
        'sigma_max_factor': 1.1,
        'sigma_max_offset': 1e-15,
        
        # Gamma
        'gamma_min_factor': 0.99,
        'gamma_max_factor': 1.0,
        'gamma_max_offset': 1e-15
    },
    'v2': {
        # Center
        'center_min_offset': -0.01,
        'center_max_offset': 0.01,
        
        # Amplitude
        'amplitude_min_factor': 0.9,
        'amplitude_max_factor': 1.1,
        'amplitude_max_offset': 10,
        
        # Sigma
        'sigma_min_factor': 0.99,
        'sigma_max_factor': 1.1,
        'sigma_max_offset': 1e-10,
        
        # Gamma
        'gamma_min_factor': 0.99,
        'gamma_max_factor': 1.0,
        'gamma_max_offset': 1e-10
    },
    'v3': {
        # Center
        'center_min_offset': -0.03,
        'center_max_offset': 0.08,
        
        # Amplitude
        'amplitude_min_factor': 0.9,
        'amplitude_max_factor': 1.1,
        'amplitude_max_offset': 10,
        
        # Sigma
        'sigma_min_factor': 0.99,
        'sigma_max_factor': 1.1,
        'sigma_max_offset': 1e-15,
        
        # Gamma
        'gamma_min_factor': 0.99,
        'gamma_max_factor': 1.0,
        'gamma_max_offset': 1e-15
    }
}

#--------------------------------------------------------------------------------

def import_initial_values(n, folder_path):
    excel_path = Path(fr'{folder_path}\\{specimen_name}_initial.xlsx')
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
        #traceback.print_exc()
        print("----------------------")
        #sys.exit()
    
    # --- 結果の表示 ---
    print("✅ ファイルから以下のキーのデータを読み込みました:")
    print(list(all_peak_data.keys()))
    print("-" * 30)
    
    Init_pars = {}

    
    for i in range(len(peaks)):
        peak = peaks[i]
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
                Init_pars['num'] = float(first_row_values['No'])
                Init_pars[f'v{i+1}_center'] = float(first_row_values['xc'])
                Init_pars[f'v{i+1}_amplitude'] = float(first_row_values['A'])
                Init_pars[f'v{i+1}_sigma'] = float(first_row_values['wG'])/(2*math.sqrt(4*math.log(2, math.e)))
                Init_pars[f'v{i+1}_gamma'] = float(first_row_values['wL'])/2
                        
                print(f"初期値は + {Init_pars}")
                
            else:
                print(f"エラー: 指定されたキー '{peak}' はどのブロックにも見つかりませんでした。")
                
    # 1. パラメータ名のリストを定義
    param_names = ['center', 'amplitude', 'sigma', 'gamma']
    
    # 2. 空の辞書を準備
    prev_params = {}
    
    # 3. パラメータ名でループし、各リストを作成して辞書に追加
    for name in param_names:
        # リスト内包表記で値のリストを作成
        value_list = [float(Init_pars[f'v{q}_{name}']) for q in range(1, n + 1)]
        # 辞書にキーと値のペアとして追加
        prev_params[name] = value_list
                            
    return Init_pars, prev_params

Init_pars, prev_params = import_initial_values(n, folder_path)


# すべてのピークの強度の合計を求める
total_I = sum(Init_pars[f'v{k}_amplitude'] for k in range(1, n+1))

# フィッテングする回折角2thetaの範囲の最小値
th_min = 10.6
# フィッテングする回折角2thetaの範囲の最大値
th_max = 12.3


#プロットのy軸の最大値
ylim_max = Init_pars['v1_amplitude']/prev_params["gamma"][1]+300

#処理ファイルの名前リストと数
all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
cont_all_file = len(all_file)


#出力データを格納する変数の定義
all_results = np.empty((1,1+n*5), float) # https://pyming.info/2022/02/10/numpy_empty/
cur_result = np.empty((1,1+n*5), float)

# すべてのファイルで共通のピーク強度を見つけるための変数
best_v1_amplitude = None
best_total_residual = float('inf')
best_results = None
best_diff = float('inf')

rough_best_v1_amplitude = 1000

results_list = []

diff_list = []
prev_center = []
prev_sigma = []
prev_gamma = []

for q in range(1, n+1):
    print(Init_pars[f'v{q}_center'])
    

    

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

prev_integral = 0.0  # <<< 変更点: 前のファイルの積分強度を保持する変数を追加



def fit_one_file(i, sum_residual=True, plot=True, save_results=True):
    global results_list, default_fit_limits, update_list, prev_center, prev_amplitude, prev_sigma, prev_gamma,prev_params,  Init_pars, all_results, total_residual, prev_integral, In, th, current_integral, intensity_scale_factor, residual_mean, prev_residual
    
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
    
    """
    # フィッテングする回折角2thetaの範囲の最小値
    th_min = Init_pars['v3_center'] - 5.5
    # フィッテングする回折角2thetaの範囲の最大値
    th_max = Init_pars['v4_center'] + 2.0 
    """
    
    # 処理したいファイルの読み込み
    in_file_path = in_path + all_file[i]
    in_file = np.loadtxt(in_file_path, delimiter=",", dtype='float')
    
    
    # 1. フィッティング範囲内のデータを効率的に抽出
    fitting_mask = (in_file[:, 0] >= th_min) & (in_file[:, 0] <= th_max)
    fitting_data = in_file[fitting_mask]
    
    # 抽出したデータがバックグラウンド処理に必要な点数（20点）より少ない場合の処理
    if len(fitting_data) < 20:
        print(f"ファイル {all_file[i]} のフィッティング範囲に十分なデータがありません。({len(fitting_data)}点)")
        # データがない、または少ない場合は空の配列をセット
        th = np.empty((1, 0), float)
        In = np.empty((1, 0), float)
    
    """
    else:
        # 2. 両端10点の平均値からバックグラウンド直線を計算
        start_point_avg = np.mean(fitting_data[:10], axis=0)
        end_point_avg = np.mean(fitting_data[-10:], axis=0)
    
        # 直線の傾き (m) と切片 (c) を計算
        m = (end_point_avg[1] - start_point_avg[1]) / (end_point_avg[0] - start_point_avg[0])
        c = start_point_avg[1] - m * start_point_avg[0]
    
        # 3. バックグラウンドを差し引く
        background_line = m * fitting_data[:, 0] + c
        subtracted_intensity = fitting_data[:, 1] - background_line
    
        # 4. 結果を元のコードの変数 th と In に格納 (2次元配列の形式を維持)
        th = fitting_data[:, 0].reshape(1, -1)
        In = subtracted_intensity.reshape(1, -1)
    """
    th = fitting_data[:, 0].reshape(1, -1)
    In = fitting_data[:, 1].reshape(1, -1)
    #"""
    
        
    #積分強度に基づくスケールファクターを計算
    current_integral = np.trapz(In[0], th[0]) # 現在のデータの積分強度を計算
    
    if i > 0 and prev_integral > 0:
        # 前のファイルの積分強度に対する比率でスケール因子を決定
        intensity_scale_factor = current_integral / prev_integral
    else:
        # 最初のファイルの場合、スケールは1.0
        intensity_scale_factor = 1.0
    
    
    if i == 0:#１つめだけ初期値を修正
        
        """    
        # 初期値をランダムに変化させる
        for p in range(1,n+1):
            Init_pars[f"v{p}_center"] += random.uniform(-0.001, 0.001)  # 例: ±0.02 変化
            Init_pars[f"v{p}_amplitude"] *= random.uniform(0.9, 1.1) 
            Init_pars[f"v{p}_sigma"] *= random.uniform(0.999, 1.001)  # 例: 5% 変化
            Init_pars[f"v{p}_gamma"] *= random.uniform(0.999, 1.001)
        """
        
        perform_fitting()
    

    # 初期値をランダムに変化させる
    for p in range(1,n+1):
        #Init_pars[f"v{p}_center"] += random.uniform(-0.0001, 0.0001)  # 例: ±0.02 変化
        Init_pars[f"v{p}_amplitude"] *= random.uniform(0.999, 1.001) 
        #Init_pars[f"v{p}_sigma"] *= random.uniform(0.999, 1.000)  # 例: 5% 変化
        #Init_pars[f"v{p}_gamma"] *= random.uniform(0.9999, 1.0001)    

    #フィッティング開始    

    perform_fitting()


    attempt = 0  # 試行回数カウンター
    
    #残差が大きい場合の処理
    
    while residual_mean >= residual_limit and attempt < max_attempts:
        print(f"Attempt {attempt + 1}: Residual too high ({residual_mean}), adjusting initial parameters and refitting...")
        
        
        # 初期値をランダムに変化させる
        for p in range(1,n+1):
            #Init_pars[f"v{p}_center"] += random.uniform(-0.0001, 0.0001)  # 例: ±0.02 変化
            Init_pars[f"v{p}_amplitude"] *= random.uniform(0.995, 1.005) 
            #Init_pars[f"v{p}_sigma"] *= random.uniform(0.99, 1.01)  # 例: 5% 変化
            #Init_pars[f"v{p}_gamma"] *= random.uniform(0.99, 1.01)
    
        perform_fitting()
        
        print(f"Residual mean after fitting: {residual_mean}")
    
        attempt += 1  # 試行回数をカウント
        
        if residual_mean < prev_residual:
            
            
            prev_residual=residual_mean
            
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
    if residual_mean >= residual_limit:
        print(f"Max attempts reached ({max_attempts}). Residual still high ({residual_mean}). Returning to previous step.")
        
        perform_fitting()
    
    print(f"fitted{i} residual={residual_mean}")
    
    # ループ後に prev_params を更新
    prev_params={}

    prev_params = {
        name: [float(out.best_values.get(f'v{r}_{name}')) for r in range(1, n + 1)]
        for name in param_names
    }  
    
    for r in range(1, n+1):
                            
        Init_pars[f'v{r}_center'] = prev_params['center'][-1]
        Init_pars[f'v{r}_amplitude'] = prev_params['amplitude'][-1]
        Init_pars[f'v{r}_sigma'] = prev_params['sigma'][-1]
        Init_pars[f'v{r}_gamma'] = prev_params['gamma'][-1]
        
    """   
    if sum_residual:
        #残差を合計に加算
        total_residual += residual_mean
        print(f"residual_mean={residual_mean}")
        
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
        ax[1].set_ylim(-100, ylim_max/5)
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
        
            
        # リストに行データを追加
        results_list.append(cur_result[0])

def perform_fitting():
    global In,th, update_list, default_fit_limits, comps, prev_center, intensity_scale_factor, prev_amplitude, prev_sigma, prev_gamma, prev_params, Init_pars, all_results, total_residual, prev_integral, current_integral, out, Init_pars, prev_residual, residual_mean, R 
        

    # デフォルト辞書をコピー
    fit_limits = copy.deepcopy(default_fit_limits)
    
    # 入力リスト (update_list) があれば、値を更新
    if update_list:
        try:
            # 入力リストは [(トップキー, サブキー, 新しい値), ...] の形式を想定
            for peak_key, param_key, new_value in update_list:
                if peak_key in fit_limits and param_key in fit_limits[peak_key]:
                    fit_limits[peak_key][param_key] = new_value
                else:
                    # 存在しないキーが指定された場合の警告
                    print(f"Warning: Key not found or structure incorrect: ('{peak_key}', '{param_key}'). Skipping.")
    
        except (ValueError, TypeError):
            print("Warning: update_list format is incorrect (expected list of 3-element tuples). Using default limits.")
    
    # スケール因子の計算 (ステップ1と2で共通して使用)
    scaled_amplitude_guess = [amp * intensity_scale_factor for amp in prev_params['amplitude']]
    
    voigt1 = VoigtModel(prefix='v1_')
    pars = voigt1.guess(In[0], x=th[0])
    
    # スケール因子を使って初期値を設定
    scaled_amplitude_guess = [amp * intensity_scale_factor for amp in prev_params['amplitude']]
    
    for k in range(1, n+1):       
        
        pars.update(VoigtModel(prefix=f'v{k}_').make_params())
        
        # <<< 変更点: value にスケーリングした値を設定
        pars[f'v{k}_center'].set(value=Init_pars[f"v{k}_center"], min=prev_params['center'][k-1]+fit_limits[f"v{k}"]["center_min_offset"], max=prev_params['center'][k-1]+fit_limits[f"v{k}"]["center_max_offset"])
        pars[f'v{k}_amplitude'].set(value=scaled_amplitude_guess[k-1], min = max(0, scaled_amplitude_guess[k-1]*fit_limits[f"v{k}"]["amplitude_min_factor"]), max = scaled_amplitude_guess[k-1]*fit_limits[f"v{k}"]["amplitude_max_factor"]+fit_limits[f"v{k}"]["amplitude_max_offset"]) # v1 の強度を固定
        pars[f'v{k}_sigma'].set(value=Init_pars[f"v{k}_sigma"], min=prev_params['sigma'][k-1]*fit_limits[f"v{k}"]["sigma_min_factor"], max=prev_params['sigma'][k-1]*fit_limits[f"v{k}"]["sigma_max_factor"]+fit_limits[f"v{k}"]["sigma_max_offset"])
        pars[f'v{k}_gamma'].set(value=Init_pars[f"v{k}_gamma"], min=prev_params['gamma'][k-1]*fit_limits[f"v{k}"]["gamma_min_factor"], max=prev_params['gamma'][k-1]*fit_limits[f"v{k}"]["gamma_max_factor"]+fit_limits[f"v{k}"]["gamma_max_offset"])
    
    mod = voigt1
    for l in range(2, n+1):
        mod += VoigtModel(prefix=f'v{l}_')

    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    
    residual_mean = np.mean(np.abs(out.residual))
      
    # <<< 変更点: 次のサイクルのために積分強度を保存
    prev_integral = current_integral

all_results = np.empty((0, 1 + n * 5), dtype=object)  # 初期化
    


# フィッティング開始

# ステップ1:初期値から逆向き
intensity_scale_factor = 0


for i in reversed(range(DIMT_onset_num, target_index+1)):
    #Init_pars["v2_center"] += 0.005
    fit_one_file(i, sum_residual=True, plot=True, save_results=True)
    #print(f"fitted{i+1}")

"""
prev_params['amplitude'][1] = 0
Init_pars["v2_amplitude"] = 0


for i in reversed(range(0, DIMT_onset_num+10)):
    prev_params['amplitude'][1] = 0
    fit_one_file(i, sum_residual=True, plot=True, save_results=True)
 
    
# ステップ2: 初期値から最後まで

"""
#一旦初期値をリセット
Init_pars, prev_params = import_initial_values(n, folder_path)

intensity_scale_factor = 0

for i in range(target_index+1, 174): #cont_all_file
    fit_one_file(i, sum_residual=True, plot=True, save_results=True)
    
    #print("fitted:", all_results[-1, 0])
    print(prev_params['gamma'])


    
# ループ終了後、リストからNumPy配列に変換
all_results = np.array(results_list)

#1番左の列 ([:, 0]) を基準に、降順でソートするためのインデックスを取得
sorted_indices = np.argsort(all_results[:, 0])

#取得したインデックスの順に配列の行を並び替える
sorted_all_results = all_results[sorted_indices]

# まず、先頭の 'num' だけでリストを初期化
col = ['num']


# peaks リストの各要素（ピーク名）に対してループ
for peak_name in peaks:
    # 関連する5つのカラム名をリストに追加
    col.extend([f'2th_{peak_name}', f'I_{peak_name}', f'FWHM_{peak_name}', f'sigma_{peak_name}',f'gamma_{peak_name}'])

print(col)

df = pd.DataFrame(sorted_all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/ 

#パラメータの描画
fig, ax = plt.subplots(3*n,1,dpi=130)
ax=ax.ravel()

print(df)

for i in range(0, n):
    ax[0+i*3].plot(df["num"], df[col[1+i*5]], '.', label=col[1+i*5]) # https://pythondatascience.plavox.info/pandas/%E8%A1%8C%E3%83%BB%E5%88%97%E3%81%AE%E6%8A%BD%E5%87%BA
    ax[1+i*3].plot(df["num"], df[col[2+i*5]], '.', label=col[2+i*5])
    ax[2+i*3].plot(df["num"], df[col[3+i*5]], '.', label=col[3+i*5]) 

    ax[0+i*3].legend()
    ax[1+i*3].legend()
    ax[2+i*3].legend()
  
plt.show()
    
    

#外部ファイルに出力
    
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
        actual_name = writer.book.sheetnames[-1]
        print(f"シート '{actual_name}' に保存しました。")

    print("保存完了")

actual_name = writer.book.sheetnames[-1]


#パラメータの描画
fig, ax = plt.subplots(3*n,1,dpi=130)
ax=ax.ravel()

for i in range(0, n):
    ax[0+i*3].plot(df["num"], df[col[1+i*5]], '.', label=col[1+i*5]) # https://pythondatascience.plavox.info/pandas/%E8%A1%8C%E3%83%BB%E5%88%97%E3%81%AE%E6%8A%BD%E5%87%BA
    ax[1+i*3].plot(df["num"], df[col[2+i*5]], '.', label=col[2+i*5])
    ax[2+i*3].plot(df["num"], df[col[3+i*5]], '.', label=col[3+i*5]) 

    ax[0+i*3].legend()
    ax[1+i*3].legend()
    ax[2+i*3].legend()
  
plt.show()