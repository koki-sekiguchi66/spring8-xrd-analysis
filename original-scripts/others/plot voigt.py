# -*- coding: utf-8 -*-
"""
Created on Fri Jun 20 15:33:53 2025

@author: harad
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
from scipy.special import voigt_profile
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Voigt関数ユーティリティ ---
def fwhm_to_sigma(fwhm_G):
    return fwhm_G / (2 * np.sqrt(2 * np.log(2)))

def fwhm_to_gamma(fwhm_L):
    return fwhm_L / 2

def single_voigt(x, x0, A, fwhm_G, fwhm_L):
    sigma = fwhm_to_sigma(fwhm_G)
    gamma = fwhm_to_gamma(fwhm_L)
    return A * voigt_profile(x - x0, sigma, gamma)

# --- メインアプリケーション ---
class VoigtApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Voigt Function Plotter")

        # 初期パラメータ
        self.max_peaks = 10
        self.entries = []
        self.n_peaks = tk.IntVar(value=3)

        # プロット範囲
        self.xmin = tk.DoubleVar(value=0.0)
        self.xmax = tk.DoubleVar(value=20.0)

        self.setup_widgets()
        self.build_inputs()

        self.plot_voigt()

    def setup_widgets(self):
        # 入力フレーム
        self.input_frame = tk.Frame(self.master)
        self.input_frame.pack(side=tk.LEFT, padx=10, pady=10)

        # ピーク数の選択
        peak_frame = tk.Frame(self.input_frame)
        peak_frame.pack(pady=5)
        tk.Label(peak_frame, text="ピーク数:").pack(side=tk.LEFT)
        self.peak_selector = ttk.Combobox(peak_frame, textvariable=self.n_peaks, width=3, state='readonly')
        self.peak_selector['values'] = list(range(1, self.max_peaks + 1))
        self.peak_selector.bind("<<ComboboxSelected>>", lambda e: self.build_inputs())
        self.peak_selector.pack(side=tk.LEFT)

        # プロット範囲設定
        range_frame = tk.Frame(self.input_frame)
        range_frame.pack(pady=5)
        tk.Label(range_frame, text="x min").pack(side=tk.LEFT)
        tk.Entry(range_frame, textvariable=self.xmin, width=6).pack(side=tk.LEFT)
        tk.Label(range_frame, text="x max").pack(side=tk.LEFT)
        tk.Entry(range_frame, textvariable=self.xmax, width=6).pack(side=tk.LEFT)

        # 「更新」ボタン
        self.update_button = tk.Button(self.input_frame, text="更新", command=self.plot_voigt)
        self.update_button.pack(pady=10)

        # グラフ領域
        self.figure = plt.Figure(figsize=(6, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.master)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def build_inputs(self):
        # 既存のエントリ削除
        for widget in self.input_frame.winfo_children():
            if isinstance(widget, tk.Frame) and "Peak" in widget.winfo_children()[0].cget("text"):
                widget.destroy()
        self.entries.clear()

        # 各ピークの入力欄生成
        for i in range(self.n_peaks.get()):
            frame = tk.Frame(self.input_frame)
            frame.pack(pady=2)
            tk.Label(frame, text=f"Peak {i+1}").pack(side=tk.LEFT, padx=3)
            row = []
            for label, default in zip(["x0", "A", "FWHM_G", "FWHM_L"], [5 + i * 5, 1.0, 0.6, 0.4]):
                tk.Label(frame, text=label).pack(side=tk.LEFT)
                entry = tk.Entry(frame, width=5)
                entry.insert(0, str(default))
                entry.pack(side=tk.LEFT, padx=2)
                row.append(entry)
            self.entries.append(row)

        self.plot_voigt()  # 入力変更直後に更新

    def plot_voigt(self):
        try:
            x = np.linspace(self.xmin.get(), self.xmax.get(), 1000)
        except tk.TclError:
            return  # 範囲が未入力のとき

        y_total = np.zeros_like(x)
        self.ax.clear()

        for i, (x0_e, A_e, fwhmG_e, fwhmL_e) in enumerate(self.entries):
            try:
                x0 = float(x0_e.get())
                A = float(A_e.get())
                fwhm_G = float(fwhmG_e.get())
                fwhm_L = float(fwhmL_e.get())
                y = single_voigt(x, x0, A, fwhm_G, fwhm_L)
                y_total += y
                self.ax.plot(x, y, '--', label=f'Peak {i+1}')
            except ValueError:
                continue  # 入力不備がある場合はスキップ

        self.ax.plot(x, y_total, label="Sum", color="black", linewidth=2)
        self.ax.set_xlabel("x")
        self.ax.set_ylabel("Intensity")
        self.ax.set_title("Sum of Voigt Functions")
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()

# 実行部
if __name__ == "__main__":
    root = tk.Tk()
    app = VoigtApp(root)
    root.mainloop()
