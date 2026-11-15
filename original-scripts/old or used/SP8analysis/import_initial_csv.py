# -*- coding: utf-8 -*-
"""
Created on Fri Oct 10 09:31:26 2025

@author: harad
"""

import pandas as pd
import sys
import traceback
from pathlib import Path
import math

# 1. パラメータ設定
excel_path = Path(r"F:\修士データ\SP8\diffraction data\20251003\0.8C95CR2\0.8C95CR2_initial.xlsx")
sub_header_marker = 'y0'

peaks=["fcc200", "fcc220", "bcc211", "fcc311"]  #解析したいピークを入力（1度以上離れた単一のピークのみ解析可能）"fcc200", "fcc220", "bcc211", "fcc311"
peak = "bcc211"

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

        # ★★★ ここからが変更点 ★★★
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
        # ★★★ 変更点ここまで ★★★


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
        Init_pars['num'] = int(first_row_values['No'])
        Init_pars['v1_center'] = int(first_row_values['xc'])
        Init_pars['v1_amplitude'] = int(first_row_values['A'])
        Init_pars['v1_sigma'] = int(first_row_values['wG'])/(2*math.sqrt(4*math.log(2, math.e)))
        Init_pars['v1_gamma'] = int(first_row_values['wL'])/2
        FWHM_initial=int(first_row_values['FWHM'])
        
        print(Init_pars)
    
    else:
        print(f"エラー: 指定されたキー '{peak}' はどのブロックにも見つかりませんでした。")