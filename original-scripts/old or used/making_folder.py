# -*- coding: utf-8 -*-
"""
Created on Mon Jul  8 14:45:02 2024

@author: harad
"""

import os

#作成するディレクトリのpathを指定
make_dir_path = 'F:/DIC-SP8/20240606SP8DIC/0.6C90%CR'

#作成しようとしているディレクトリが存在するかどうかを判定する
if os.path.isdir(make_dir_path):
    #既にディレクトリが存在する場合は何もしない
    pass
else:
    #ディレクトリが存在しない場合のみ作成する
    os.makedirs(make_dir_path)