# -*- coding: utf-8 -*-
"""
Created on Fri Nov 29 13:39:12 2024

@author: harad
"""
#使用したい環境に　pip install opencv-python　しておく

#動画ファイルの指定した範囲を画像ファイルに変換するプログラム
#指定したフォルダ内のすべての動画ファイルを纏めて変換

import cv2
import os
from pathlib import Path

def save_frame_range_sec(video_path, start_sec, stop_sec, step_sec,
                         dir_path, basename, ext='jpg'):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return

    os.makedirs(dir_path, exist_ok=True)
    base_path = os.path.join(dir_path, basename)

    digit = len(str(int(cap.get(cv2.CAP_PROP_FRAME_COUNT))))

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps_inv = 1 / fps

    sec = start_sec
    while sec < stop_sec:
        n = round(fps * sec)
        cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(
                '{}_{}_{:.0f}.{}'.format(
                    base_path, str(n).zfill(digit), n * fps_inv, ext
                ),
                frame
            )
        else:
            return
        sec += step_sec

file_place=Path(r'G:\DIC')
#フォルダパス

files = os.listdir(file_place)

MP4_files = [s for s in files if 'MP4' in s]


for i in range(len(MP4_files)):
    MP4_file_name=MP4_files[i].removesuffix('.MP4')
    save_frame_range_sec(f"{file_place}\\{MP4_file_name}.mp4",7.9, 3000, 0.2, f"{file_place}\\{MP4_file_name}", MP4_file_name+'_img')
 #(ビデオファイルの場所、開始時間、終了時間、間隔、保存フォルダ場所、画像ファイル名)

print('finished')