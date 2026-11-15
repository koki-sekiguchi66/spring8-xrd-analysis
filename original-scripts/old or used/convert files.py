# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 16:58:54 2025

@author: harad
"""
import os
import shutil

def list_folders_in_directory(directory_path):
    """
    指定したディレクトリ内のフォルダ名をリストとして取得する。

    Args:
        directory_path (str): 対象のディレクトリのパス。

    Returns:
        list: フォルダ名のリスト。
    """
    try:
        # ディレクトリ内の要素を取得し、フォルダのみを選択
        folder_names = [
            item for item in os.listdir(directory_path)
            if os.path.isdir(os.path.join(directory_path, item))
        ]
        return folder_names
    except FileNotFoundError:
        print(f"指定されたディレクトリが見つかりません: {directory_path}")
        return []
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return []

def copy_and_rename_files(source_dir, destination_dir, old_ext, new_ext):
    """
    指定したフォルダから特定の拡張子を持つファイルをコピーし、
    拡張子を変更して新しいフォルダに保存する。

    Args:
        source_dir (str): ソースフォルダのパス。
        destination_dir (str): 保存先フォルダのパス。
        old_ext (str): 現在の拡張子（例: ".tth"）。
        new_ext (str): 新しい拡張子（例: ".txt"）。
    """
    # 保存先フォルダが存在しない場合は作成
    os.makedirs(destination_dir, exist_ok=True)

    # ソースフォルダ内のすべてのファイルを処理
    for filename in os.listdir(source_dir):
        if filename.endswith(old_ext):  # 指定された拡張子を持つファイルを選択
            old_file_path = os.path.join(source_dir, filename)
            new_filename = filename.replace(old_ext, new_ext)
            new_file_path = os.path.join(destination_dir, new_filename)

            # ファイルをコピーして拡張子を変更
            shutil.copy(old_file_path, new_file_path)
            
# 使用例
directory = "F:\\修士データ\\SP8\\diffraction data\\0.5C\\"  # 対象のフォルダのパスを指定
folders = list_folders_in_directory(directory)
destination_folder = directory  # 保存先フォルダのパス

for i in range(len(folders)):
    folder_path=destination_folder+folders[i]
    if os.path.isdir(destination_folder+folders[i]+"\\txt\\") is True and len(os.listdir(folder_path+"\\tth\\"))==len(os.listdir(folder_path+"\\txt\\")):
        print(folders[i]+"has already converted")
        #txtフォルダがあって、txtファイルの数も足りている場合スキップ
        
    else:
        try:
            # 拡張子変更とコピーを実行
            copy_and_rename_files(folder_path+"\\tth\\", folder_path+"\\txt\\", ".tth", ".txt")
            
        except FileNotFoundError as e:
            print(e)
        else:
            print("finished "+folders[i])







