# -*- coding: utf-8 -*-
"""
Created on Mon Jul  8 14:31:20 2024

@author: harad
"""

#使用したい環境に　pip install opencv-python　しておく

#動画ファイルの指定した範囲を画像ファイルに変換するプログラム


import cv2
import os

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

file_place="I:\\DIC_SP8\\240606_oishi\\"
#フォルダパス'F:/DIC-SP8/GaoDIC/0.6C_90CR/'
file_name='P1370763'
#変換したい動画ファイルの名前（拡張子.mp4は不要）

#print(file_place+'/'+file_name +'.mp4')

save_frame_range_sec(file_place+file_name +'.mp4', 0,670, 1, file_place+file_name, file_name+'_img')

#(ビデオファイルの場所、開始時間、終了時間、間隔、保存フォルダ場所、画像ファイル名)