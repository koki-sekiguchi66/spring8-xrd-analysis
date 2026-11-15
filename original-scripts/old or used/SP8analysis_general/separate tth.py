# -*- coding: utf-8 -*-
"""
Created on Wed May 21 09:23:42 2025

@author: harad
"""

import os
import shutil
from pathlib import Path

# ルートディレクトリを指定
root_dir = Path(r"F:\修士データ\SP8\diffraction data\20250517")

# サブフォルダ（sampleA, sampleB, etc）を探索
for subfolder in os.listdir(root_dir):
    subfolder_path = os.path.join(root_dir, subfolder)
    if not os.path.isdir(subfolder_path):
        continue

    # tthファイルの移動先: 各サブフォルダ内の "data" フォルダ
    target_dir = os.path.join(subfolder_path, 'tth')
    os.makedirs(target_dir, exist_ok=True)

    # サブフォルダ内のすべてのフォルダを再帰的に探索
    for dirpath, dirnames, filenames in os.walk(subfolder_path):
        # "data" フォルダ自身はスキップ（既に移動先）
        if os.path.abspath(dirpath) == os.path.abspath(target_dir):
            continue
        elif len(os.listdir(dirpath)) < 50 :
            continue
        for filename in filenames:
            if filename.lower().endswith('.tth'):
                src_path = os.path.join(dirpath, filename)
                dst_path = os.path.join(target_dir, filename)
                shutil.move(src_path, dst_path)
                print(f"Moved: {src_path} → {dst_path}")
