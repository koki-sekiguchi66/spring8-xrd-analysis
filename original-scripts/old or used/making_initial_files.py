# -*- coding: utf-8 -*-
"""
Created on Wed Jul 23 09:40:22 2025

@author: harad
"""

import os
import openpyxl


specimen_name = "1.0CLN2"
peaks = ["fcc111bcc110", "fcc110bct011bct110", "fcc200", "fcc220", "bcc211", "fcc311"]

# 1. 基本情報を設定
folder_path = os.path.join(os.path.expanduser("~"), r"F:\修士データ\SP8\diffraction data\20250710\1.0CLN2")
file_names = [f"{specimen_name}_{peak}_initial.xlsx" for peak in peaks]

# 書き込むデータを3行分定義
# 1行目: A1は空白、B1から列番号
row1_data = [] + list(range(20))
# 2行目: A2に行番号「1」、B2からヘッダー
row2_data = [1, "No", "y0", "xc", "A", "wG", "wL", "FWHM", "y0", "xc", "A", "wG", "wL", "FWHM", "y0", "xc", "A", "wG", "wL", "FWHM"]
# 3行目: A3に行番号「2」
row3_data = [2]

# 2. フォルダが存在しない場合は作成
os.makedirs(folder_path, exist_ok=True)

# 3. ファイルを1つずつ作成してデータを書き込む
for file_name in file_names:
  file_path = os.path.join(folder_path, file_name)

  # --- ここからが変更点 ---
  # もし、同じ名前のファイルが存在しない場合のみ、以降の作成処理を実行
  if not os.path.exists(file_path):
    # 新規Excelブックを作成
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    # 定義したデータを順番に書き込む
    sheet.append(row1_data)
    sheet.append(row2_data)
    sheet.append(row3_data)

    # ファイルを保存
    workbook.save(file_path)

    print(f"新規作成: {file_path}")
  # もし、すでにファイルが存在する場合
  else:
    print(f"スキップ: {file_path} は既に存在します。")
  # --- ここまでが変更点 ---


print("\n処理が完了しました。")