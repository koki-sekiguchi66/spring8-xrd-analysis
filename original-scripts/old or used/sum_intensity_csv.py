# -*- coding: utf-8 -*-
"""
Created on Thu Dec 12 11:02:54 2024

@author: harad
"""
import os
import polars as pl
import glob

# 入力ディレクトリ
in_path_copy = r'F:\修士データ\SP8\diffraction data\1.0C\25CR\bcg_removed'
in_path = os.path.normpath(in_path_copy)  # パスを正規化

initial_file_num="1"
final_file_num="20"

# 出力ファイルの設定
output_directory = r'F:\修士データ\SP8\diffraction data\1.0C\25CR'
output_file = os.path.join(output_directory, "sums_output"+initial_file_num+"-"+final_file_num+".csv")

# 辞書を用意
data_dict = {}

# ファイルパスを取得
file_paths = glob.glob(f"{in_path}/*.csv")[int(initial_file_num)-1:int(final_file_num)-1]  # initial_file_num番目からfinal_file_num番目までのファイルを対象

# 各CSVファイルを読み込み辞書に保存
for file_path in file_paths:
    # CSVをDataFrame（polars）として読み込む
    df = pl.read_csv(file_path, has_header=False)  # ヘッダーがない場合
    # ファイル名をキーに使用
    key = file_path.split('/')[-1].replace('bcg', '').replace('.csv', '')
    data_dict[key] = df

# 各行ごとにデータを集計
sums = {}
row_count = len(next(iter(data_dict.values())))  # 最初のDataFrameの行数を取得

for i in range(row_count):
    row_sum = 0
    for key, df in data_dict.items():
        row_sum += df[i, 1]  # 2列目を集計（polarsのインデックスは0始まり）
    sums[data_dict[key][i, 0]] = row_sum  # 1列目の値をキーに、合計を値として保存

# sumsをCSVに出力

# 辞書をpolars DataFrameに変換して保存
sums_df = pl.DataFrame({"Key": list(sums.keys()), "Sum": list(sums.values())})
sums_df.write_csv(output_file,include_header=False)

print(f"Saved sums to {output_file}")
    
# sumsをCSVに出力







# 辞書の中身を確認
'''
for key, value in data_dict.items():
    print(f"Key: {key}")
    print(value.head())  # 各DataFrameの先頭数行を表示
'''