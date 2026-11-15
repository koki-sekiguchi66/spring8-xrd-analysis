# -*- coding: utf-8 -*-
"""
単一ピーク fitting（Voigt + 線形バックグラウンド）  ver4.0
原田さん ver3.1 をベースに以下を修正
  [1] Origin wG -> sigma 換算を修正（wG = 2*sqrt(2ln2)*sigma）
  [2] FWHM を lmfit の正しい式（gamma, sigma を代入）で計算
  [3] gamma を vary=True にして Lorentz 幅も実際に fitting
  [4] 再試行で「最良」の結果を採用（旧版は最後の試行を採用していた）
  [5] 後半方向（target 以降）の fitting を初期値から開始
  [6] 中心位置の範囲を絶対値（deg/frame）で指定
  [7] 新相ピーク（α'など）は変態開始前を強度0に固定し、開始点から fitting
  [8] fitting 範囲を FWHM に応じて拡張（隣接ピークを避ける上下限を指定可）
  [9] バックグラウンドは複数ピーク版と同じ線形に統一
  [10] 乱数シード固定・フレームごとの残差を出力
必要モジュール: lmfit, numpy, pandas, matplotlib, openpyxl
"""
import math
import os
import random
import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lmfit.models import LinearModel, VoigtModel

# =============================== 入力 ===============================
folder_path = Path(r"F:\SPring8\20261111\XRD\Seki_age_2_tensile")  # bcg_removed のあるフォルダ
specimen_name = "1100C10min_700C600min"   # {specimen_name}_initial.xlsx が必要
bcg_folder_name = "bcg_removed_arpls"

peaks = ["fcc200", "fcc220", "fcc311", "bcc112", "bcc321"]  # 1度以上離れた単一ピーク

# 新相ピーク: {ピーク名: 変態開始 num}。開始前は強度0として出力し fitting しない
new_phase_onset = {"bcc112": 213, "bcc321": 213}

# fitting 範囲の絶対上下限（隣接ピークを含めないため）。指定なしは中心±自動幅
window_limits = {
    "bcc321": (30.1, 31.7),   # fcc420(~29.85) と fcc422(~32.8) を避ける
    "bcc112": (19.4, 20.7),
}
window_min_half = 0.5     # 範囲の最小半幅 [deg]
window_fwhm_mult = 2.0    # 範囲の半幅 = max(min_half, mult*FWHM)

# 1フレームあたりの変化の上限（前フレームの値に対して）
center_step = 0.02        # 中心位置 ±[deg]
#   ※ 狭くしすぎると Gauss/Lorentz 成分の配分が少しずつ漂流し、面積が最大20%程度偏る
#     （合成データで確認）。前フレームは「出発点」として使い、範囲は広めにする
amp_factor = (0.80, 1.25) # 振幅 ×
amp_offset = 5.0          # 振幅 ± の絶対余裕（弱いピークの立ち上がり用）
width_factor = (0.70, 1.40)  # sigma, gamma ×
width_offset = 1e-4       # sigma, gamma ± の絶対余裕 [deg]
new_phase_init_amp = 1.0  # 新相ピークの開始時の振幅初期値

residual_limit = 0.8      # 相対残差の許容値（RMS残差 / 平均|I|）
max_attempts = 20
random.seed(0)

plot_every = 50           # 何フレームごとに fitting 結果を描画するか（0で描画なし）
# ====================================================================

LN2 = math.log(2)
WG_PER_SIGMA = 2 * math.sqrt(2 * LN2)  # Gauss FWHM / sigma = 2.3548
trapz = getattr(np, "trapezoid", None) or np.trapz


def voigt_fwhm(sigma, gamma):
    """lmfit VoigtModel と同じ近似式（sigma: Gauss σ, gamma: Lorentz HWHM）"""
    return 1.0692 * gamma + math.sqrt(0.8664 * gamma ** 2 + 5.545083 * sigma ** 2)


def file_num(fname):
    """ファイル名末尾の数字を num とする（例: xxx_0213bcg.csv -> 213）"""
    return int(re.findall(r"\d+", Path(fname).stem)[-1])


def read_initial(excel_path):
    """Origin の初期値ファイル（ピーク名行 + 'y0'等のサブヘッダ行）を読む"""
    raw = pd.read_excel(excel_path, header=None, engine="openpyxl")
    sub_rows = raw.index[raw.astype(str).apply(lambda c: c.str.strip().eq("y0")).any(axis=1)]
    if len(sub_rows) == 0:
        raise ValueError("初期値ファイルに 'y0' のヘッダ行が見つかりません")
    init = {}
    for r in sub_rows:
        names = raw.iloc[r - 1].ffill()
        subs = raw.iloc[r]
        vals = raw.iloc[r + 1]
        no = vals[subs[subs.astype(str).str.strip() == "No"].index[0]]
        for peak in names.dropna().unique():
            cols = names.index[names == peak]
            d = {str(subs[c]).strip(): vals[c] for c in cols}
            if pd.isna(d.get("xc")):
                continue
            init[peak] = dict(num=int(no), center=float(d["xc"]), amplitude=float(d["A"]),
                              sigma=float(d["wG"]) / WG_PER_SIGMA,   # [1]
                              gamma=float(d["wL"]) / 2,
                              y0=float(d.get("y0", 0) or 0))
    return init


def bounded(value, lo, hi):
    return min(max(value, lo), hi)


def fit_frame(th, In, prev, fixed_zero=False):
    """1フレームを fitting。prev: 前フレームの {center, amplitude, sigma, gamma}"""
    model = VoigtModel(prefix="v1_") + LinearModel(prefix="bkg_")
    best = None
    for attempt in range(max_attempts + 1):
        jitter = attempt > 0
        p = model.make_params()
        c_lo, c_hi = prev["center"] - center_step, prev["center"] + center_step
        c0 = prev["center"] + (random.uniform(-0.3, 0.3) * center_step if jitter else 0)
        p["v1_center"].set(value=bounded(c0, c_lo, c_hi), min=c_lo, max=c_hi,
                           vary=not fixed_zero)

        a_lo = max(0.0, prev["amplitude"] * amp_factor[0] - amp_offset)
        a_hi = prev["amplitude"] * amp_factor[1] + amp_offset
        a0 = prev["amplitude"] * (random.uniform(0.95, 1.05) if jitter else 1)
        p["v1_amplitude"].set(value=bounded(a0, a_lo, a_hi), min=a_lo, max=a_hi,
                              vary=not fixed_zero)
        if fixed_zero:
            p["v1_amplitude"].set(value=0.0, vary=False)

        for name in ("sigma", "gamma"):
            lo = max(1e-6, prev[name] * width_factor[0] - width_offset)
            hi = prev[name] * width_factor[1] + width_offset
            v0 = prev[name] * (random.uniform(0.97, 1.03) if jitter else 1)
            p[f"v1_{name}"].set(value=bounded(v0, lo, hi), min=lo, max=hi,
                                vary=not fixed_zero, expr=None)          # [3]
        p["bkg_slope"].set(value=0.0)
        p["bkg_intercept"].set(value=float(np.mean(np.r_[In[:5], In[-5:]])))

        out = model.fit(In, p, x=th)
        rel = math.sqrt(np.mean(out.residual ** 2)) / max(np.mean(np.abs(In)), 1e-12)
        if best is None or rel < best[1]:                               # [4]
            best = (out, rel, attempt)
        if rel < residual_limit or fixed_zero:
            break
    return best


def frame_window(peak, prev):
    fwhm = voigt_fwhm(prev["sigma"], prev["gamma"])
    half = max(window_min_half, window_fwhm_mult * fwhm)                 # [8]
    lo, hi = prev["center"] - half, prev["center"] + half
    if peak in window_limits:
        lo, hi = max(lo, window_limits[peak][0]), min(hi, window_limits[peak][1])
    return lo, hi


def plot_fit(th, In, out, title):
    fig, ax = plt.subplots(dpi=100, figsize=(7, 4))
    ax.plot(th, In, "o", ms=3, color="gray", label="data")
    ax.plot(th, out.best_fit, "-", lw=2, label="fit")
    comps = out.eval_components(x=th)
    ax.plot(th, comps["v1_"] + comps["bkg_"], "--", label="Voigt+bkg")
    ax.plot(th, comps["bkg_"], ":", label="bkg")
    ax.set(title=title, xlabel="2θ (deg)", ylabel="Intensity")
    ax.legend()
    plt.tight_layout()
    plt.show()
    plt.close(fig)


def run_peak(peak, init, files, in_dir):
    nums = [file_num(f) for f in files]
    t_idx = nums.index(init["num"]) if init["num"] in nums else None
    if t_idx is None:
        raise ValueError(f"{peak}: 初期値の num={init['num']} のファイルがありません")
    onset = new_phase_onset.get(peak)
    rows = {}
    start = dict(center=init["center"], amplitude=init["amplitude"],
                 sigma=init["sigma"], gamma=init["gamma"])

    def do(idx, prev):
        num = nums[idx]
        before_onset = onset is not None and num < onset
        data = np.loadtxt(in_dir / files[idx], delimiter=",")
        lo, hi = frame_window(peak, prev)
        m = (data[:, 0] >= lo) & (data[:, 0] <= hi)
        th, In = data[m, 0], data[m, 1]
        if len(th) < 15:
            print(f"{peak} num={num}: 範囲内のデータ点不足 ({len(th)})")
            return prev
        out, rel, att = fit_frame(th, In, prev, fixed_zero=before_onset)
        bv = out.best_values
        s, g = bv["v1_sigma"], bv["v1_gamma"]
        rows[num] = [num, bv["v1_center"], bv["v1_amplitude"], voigt_fwhm(s, g),     # [2]
                     s * WG_PER_SIGMA, 2 * g, bv["bkg_slope"], bv["bkg_intercept"],
                     rel, att, int(before_onset)]
        if plot_every and (len(rows) % plot_every == 0):
            plot_fit(th, In, out, f"{peak}  num={num}  rel.res={rel:.3f}")
        if before_onset:
            return prev
        return dict(center=bv["v1_center"], amplitude=bv["v1_amplitude"], sigma=s, gamma=g)

    # 前半方向: target -> 先頭（新相は開始点で止め、それより前は強度0）
    prev = dict(start)
    for idx in reversed(range(0, t_idx + 1)):
        prev = do(idx, prev)
    # 後半方向: 初期値に戻してから target+1 -> 最後                    # [5]
    prev = dict(start)
    for idx in range(t_idx + 1, len(files)):
        prev = do(idx, prev)

    cols = ["num", f"2th_{peak}", f"I_{peak}", f"FWHM_{peak}", f"wG_{peak}", f"wL_{peak}",
            f"bkgslope_{peak}", f"bkgint_{peak}", f"relres_{peak}", f"attempts_{peak}",
            f"fixed0_{peak}"]
    df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=cols)
    if onset is not None:   # 変態開始前は幅・位置を出力しない
        pre = df["num"] < onset
        df.loc[pre, [f"2th_{peak}", f"FWHM_{peak}", f"wG_{peak}", f"wL_{peak}"]] = np.nan
        df.loc[pre, f"I_{peak}"] = 0.0
    return df


def save(df, out_path, sheet):
    try:
        mode = "a" if out_path.exists() else "w"
        kw = dict(if_sheet_exists="new") if mode == "a" else {}
        with pd.ExcelWriter(out_path, engine="openpyxl", mode=mode, **kw) as w:
            df.to_excel(w, sheet_name=sheet, index=False)
        print(f"保存: {out_path} [{sheet}]")
    except PermissionError:
        alt = out_path.with_name(out_path.stem + f"_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        with pd.ExcelWriter(alt, engine="openpyxl") as w:
            df.to_excel(w, sheet_name=sheet, index=False)
        print(f"ファイルが開かれているため別名で保存: {alt}")


def summary_plot(df, peak):
    fig, ax = plt.subplots(4, 1, figsize=(7, 8), dpi=100, sharex=True)
    for a, col in zip(ax, ["2th", "I", "FWHM", "relres"]):
        a.plot(df["num"], df[f"{col}_{peak}"], ".", ms=2)
        a.set_ylabel(col)
    ax[0].set_title(peak)
    ax[-1].set_xlabel("num")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    in_dir = folder_path / bcg_folder_name
    files = sorted(os.listdir(in_dir), key=file_num)
    init_all = read_initial(folder_path / f"{specimen_name}_initial.xlsx")
    out_path = folder_path / f"{specimen_name}output.xlsx"
    for peak in peaks:
        if peak not in init_all:
            print(f"初期値ファイルに {peak} がないためスキップ")
            continue
        print(f"=== {peak} : 初期値 {init_all[peak]} ===")
        df = run_peak(peak, init_all[peak], files, in_dir)
        save(df, out_path, peak)
        summary_plot(df, peak)
