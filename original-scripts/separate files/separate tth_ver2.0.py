# -*- coding: utf-8 -*-
"""
Created on Wed Jul 16 11:42:30 2025

@author: harad
"""

import os
import shutil
from pathlib import Path

# ルートディレクトリを指定
# 例: r"C:\Users\YourName\Desktop\data_root"
#ルート内のすべてのフォルダに対してtthファイルの仕分けを行う

root_dir = Path(r"F:\修士データ\SP8\diffraction data\20251114\Gao")

# サブフォルダ（sampleA, sampleB, etc）を探索
for subfolder in root_dir.iterdir():
    if not subfolder.is_dir():
        continue

    # 1. 移動先のフォルダを定義・作成
    # .tthファイル用のフォルダ
    tth_target_dir = subfolder / 'tth'
    # それ以外のファイル用のフォルダ
    others_target_dir = subfolder / 'others'
    
    tth_target_dir.mkdir(exist_ok=True)
    others_target_dir.mkdir(exist_ok=True)
    
    print(f"--- Processing {subfolder.name} ---")

    # サブフォルダ内のすべてのフォルダを再帰的に探索
    for dirpath, dirnames, filenames in os.walk(subfolder):
        current_dir_path = Path(dirpath)

        # 2. 移動先フォルダ自体は探索対象から除外する
        # これにより、移動させたファイルを再度移動しようとするのを防ぐ
        if current_dir_path.resolve() == tth_target_dir.resolve() or \
           current_dir_path.resolve() == others_target_dir.resolve():
            dirnames.clear()  # このフォルダ配下は探索しない
            continue

        # 元のコードにあった条件を維持
        if len(os.listdir(current_dir_path)) < 50:
            continue
            
        # 3. ファイルを拡張子によって振り分け
        for filename in filenames:
            src_path = current_dir_path / filename
            
            # .tthファイルかどうかで移動先を決定
            if filename.lower().endswith('.tth'):
                dst_path = tth_target_dir / filename
            else:
                dst_path = others_target_dir / filename
            
            # ファイルを移動
            try:
                shutil.move(src_path, dst_path)
                print(f"Moved: {src_path} -> {dst_path}")
            except shutil.Error as e:
                # 移動先に同名ファイルが既に存在する場合のエラー処理
                print(f"Could not move {src_path}. Reason: {e}")

print("--- All processes finished. ---")