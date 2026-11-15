# -*- coding: utf-8 -*-
"""
複数ピーク同時 fitting（Voigt×n + 線形バックグラウンド）  ver2.0
原田さん ver1.0.0 をベースに以下を修正
  [1] Origin wG -> sigma 換算を修正（wG = 2*sqrt(2ln2)*sigma）
  [2] FWHM を lmfit の正しい式（gamma, sigma を代入）で計算
  [3] gamma を vary=True にして Lorentz 幅も実際に fitting
  [4] 隣接ピーク間の最小間隔を 0.5° -> min_separation（既定0.05°）に変更
      （旧版は 0.5° 未満で重なるピークで下限>上限となり、lmfit が黙って入れ替えていた）
  [5] 新相ピーク（α'など）は変態開始前を強度0に固定
  [6] 重なるピークを物理的に拘束するオプション（tie）
        - 中心位置: 同じ相の基準ピーク（単一ピーク版で fitting 済み）の格子定数から計算
        - 幅: 基準ピークの sigma・gamma を tanθ 比で換算した値 × 共通スケール（範囲指定）
  [7] 再試行で最良の結果を採用・乱数シード固定・フレームごとの残差を出力
  [8] 出力列名を単一ピーク版と統一（2th_, I_, FWHM_, wG_, wL_）
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
folder_path = Path(r"F:\SPring8\20261111\XRD\Seki_age_2_tensile")
specimen_name = "1100C10min_700C600min"
bcg_folder_name = "bcg_removed_arpls"
wavelength = 0.04133   # [nm] 中心位置 tie の計算に使用

# 回折角の小さい順に並べる
peaks = ["fcc111", "bcc101"]

# 新相ピーク: {ピーク名: 変態開始 num}
new_phase_onset = {"bcc110": 213}

# fitting 範囲 [deg]（None なら 最初のピーク-margin 〜 最後のピーク+margin）
fit_range = (11.0, 12.0)
range_margin = 1.0

# 拘束（tie）の設定。不要なら空の dict に
#   ref_peak : 単一ピーク版で fitting 済みのシート名（同じ output.xlsx 内）
#   hkl / ref_hkl : 立方晶の面指数（中心位置を格子定数から計算）
#   tie_center : True なら中心 = 計算値 ± center_tol
#   width_scale : 幅 = 基準ピークの幅 × tanθ比 × scale（scale の範囲）
ties = {
    "bcc110": dict(ref_peak="bcc112", hkl=(1, 1, 0), ref_hkl=(2, 1, 1),
                   tie_center=True, center_tol=0.03, width_scale=(0.7, 1.3)),
    "fcc111": dict(ref_peak="fcc200", hkl=(1, 1, 1), ref_hkl=(2, 0, 0),
                   tie_center=False, center_tol=None, width_scale=(0.3, 1.2)),
}

min_separation = 0.05   # 隣接ピーク中心の最小間隔 [deg]

# 1フレームあたりの変化の上限（tie していないパラメータに適用）
center_step = 0.01
#   ※ 狭くしすぎると Gauss/Lorentz 成分の配分が漂流して面積が偏るため広めにする
amp_factor = (0.80, 1.25)
amp_offset = 10.0
width_factor = (0.70, 1.40)
width_offset = 1e-4
new_phase_init_amp = 1.0

residual_limit = 0.8      # 相対残差（RMS残差 / 平均|I|）
max_attempts = 15
random.seed(0)
plot_every = 50
# ====================================================================

LN2 = math.log(2)
WG_PER_SIGMA = 2 * math.sqrt(2 * LN2)


def voigt_fwhm(sigma, gamma):
    return 1.0692 * gamma + math.sqrt(0.8664 * gamma ** 2 + 5.545083 * sigma ** 2)


def file_num(fname):
    return int(re.findall(r"\d+", Path(fname).stem)[-1])


def read_initial(excel_path):
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
                              sigma=float(d["wG"]) / WG_PER_SIGMA, gamma=float(d["wL"]) / 2)
    return init


def load_reference(out_path):
    """tie 用の基準ピーク（単一ピーク版の出力）を num をキーに読み込む"""
    refs = {}
    need = {t["ref_peak"] for t in ties.values()}
    if not need:
        return refs
    book = pd.read_excel(out_path, sheet_name=None)
    for rp in need:
        if rp not in book:
            raise ValueError(f"tie の基準シート {rp} が {out_path} にありません。先に単一ピーク版を実行してください")
        df = book[rp].set_index("num")
        refs[rp] = dict(center=df[f"2th_{rp}"], sigma=df[f"wG_{rp}"] / WG_PER_SIGMA,
                        gamma=df[f"wL_{rp}"] / 2)
    return refs


def tied_values(peak, num, refs):
    """基準ピークから tie 先の中心（計算値）と幅（tanθ換算）を返す。無ければ None"""
    t = ties[peak]
    r = refs[t["ref_peak"]]
    if num not in r["center"].index or pd.isna(r["center"][num]):
        return None
    tt_ref = math.radians(r["center"][num])
    d_ref = wavelength / (2 * math.sin(tt_ref / 2))
    a = d_ref * math.sqrt(sum(h * h for h in t["ref_hkl"]))
    d = a / math.sqrt(sum(h * h for h in t["hkl"]))
    tt = 2 * math.asin(wavelength / (2 * d))
    ratio = math.tan(tt / 2) / math.tan(tt_ref / 2)
    return dict(center=math.degrees(tt), sigma=r["sigma"][num] * ratio,
                gamma=r["gamma"][num] * ratio)


def bounded(v, lo, hi):
    return min(max(v, lo), hi)


def build_params(model, prev, num, refs, jitter):
    p = model.make_params()
    centers = []
    for k, peak in enumerate(peaks, start=1):
        pre = f"v{k}_"
        pv = prev[peak]
        onset = new_phase_onset.get(peak)
        zero = onset is not None and num < onset
        tv = tied_values(peak, num, refs) if (peak in ties and not zero) else None

        # 中心
        c_lo, c_hi = pv["center"] - center_step, pv["center"] + center_step
        if tv is not None and ties[peak]["tie_center"]:
            tol = ties[peak]["center_tol"]
            c_lo, c_hi = tv["center"] - tol, tv["center"] + tol
        if centers:   # 隣のピークより min_separation 以上大きい角度に     [4]
            c_lo = max(c_lo, centers[-1] + min_separation)
        if c_lo >= c_hi:
            print(f"警告 num={num} {peak}: 中心の範囲が成立しません ({c_lo:.4f} >= {c_hi:.4f})。"
                  f" min_separation か center_step を見直してください")
            c_hi = c_lo + 1e-4
        c0 = bounded(pv["center"] + (random.uniform(-0.3, 0.3) * center_step if jitter else 0),
                     c_lo, c_hi)
        p[pre + "center"].set(value=c0, min=c_lo, max=c_hi, vary=not zero)
        centers.append(c0)

        # 振幅
        if zero:
            p[pre + "amplitude"].set(value=0.0, vary=False)
        else:
            a_prev = max(pv["amplitude"], new_phase_init_amp if onset is not None else 0)
            a_lo = max(0.0, a_prev * amp_factor[0] - amp_offset)
            a_hi = a_prev * amp_factor[1] + amp_offset
            a0 = a_prev * (random.uniform(0.97, 1.03) if jitter else 1)
            p[pre + "amplitude"].set(value=bounded(a0, a_lo, a_hi), min=a_lo, max=a_hi, vary=True)

        # 幅
        if tv is not None:                                            # [6]
            s_lo, s_hi = ties[peak]["width_scale"]
            p.add(f"scale{k}", value=bounded(1.0, s_lo, s_hi), min=s_lo, max=s_hi, vary=True)
            p[pre + "sigma"].set(expr=f"{tv['sigma']:.8g}*scale{k}")
            p[pre + "gamma"].set(expr=f"{tv['gamma']:.8g}*scale{k}")
        else:
            for name in ("sigma", "gamma"):
                lo = max(1e-6, pv[name] * width_factor[0] - width_offset)
                hi = pv[name] * width_factor[1] + width_offset
                v0 = pv[name] * (random.uniform(0.98, 1.02) if jitter else 1)
                p[pre + name].set(value=bounded(v0, lo, hi), min=lo, max=hi,
                                  vary=not zero, expr=None)           # [3]
    p["bkg_slope"].set(value=0.0)
    p["bkg_intercept"].set(value=0.0)
    return p


def fit_frame(th, In, prev, num, refs):
    model = LinearModel(prefix="bkg_")
    for k in range(1, len(peaks) + 1):
        model = model + VoigtModel(prefix=f"v{k}_")
    best = None
    for attempt in range(max_attempts + 1):
        p = build_params(model, prev, num, refs, jitter=attempt > 0)
        p["bkg_intercept"].set(value=float(np.mean(np.r_[In[:5], In[-5:]])))
        out = model.fit(In, p, x=th)
        rel = math.sqrt(np.mean(out.residual ** 2)) / max(np.mean(np.abs(In)), 1e-12)
        if best is None or rel < best[1]:                             # [7]
            best = (out, rel, attempt)
        if rel < residual_limit:
            break
    return best


def plot_fit(th, In, out, title):
    fig, ax = plt.subplots(dpi=100, figsize=(7, 4))
    ax.plot(th, In, "o", ms=3, color="gray", label="data")
    ax.plot(th, out.best_fit, "-", lw=2, label="fit")
    comps = out.eval_components(x=th)
    for k, peak in enumerate(peaks, start=1):
        ax.plot(th, comps[f"v{k}_"] + comps["bkg_"], "--", label=peak)
    ax.plot(th, comps["bkg_"], ":", label="bkg")
    ax.set(title=title, xlabel="2θ (deg)", ylabel="Intensity")
    ax.legend()
    plt.tight_layout()
    plt.show()
    plt.close(fig)


def run(files, in_dir, init_all, refs):
    nums = [file_num(f) for f in files]
    t_num = init_all[peaks[0]]["num"]
    if any(init_all[p]["num"] != t_num for p in peaks):
        raise ValueError("初期値は全ピーク同じ num で用意してください")
    t_idx = nums.index(t_num)
    start = {p: dict(center=init_all[p]["center"], amplitude=init_all[p]["amplitude"],
                     sigma=init_all[p]["sigma"], gamma=init_all[p]["gamma"]) for p in peaks}
    lo = fit_range[0] if fit_range else start[peaks[0]]["center"] - range_margin
    hi = fit_range[1] if fit_range else start[peaks[-1]]["center"] + range_margin
    rows = {}

    def do(idx, prev):
        num = nums[idx]
        data = np.loadtxt(in_dir / files[idx], delimiter=",")
        m = (data[:, 0] >= lo) & (data[:, 0] <= hi)
        th, In = data[m, 0], data[m, 1]
        out, rel, att = fit_frame(th, In, prev, num, refs)
        bv = out.params
        row = [num]
        new_prev = {}
        for k, peak in enumerate(peaks, start=1):
            s, g = bv[f"v{k}_sigma"].value, bv[f"v{k}_gamma"].value
            amp = bv[f"v{k}_amplitude"].value
            row += [bv[f"v{k}_center"].value, amp, voigt_fwhm(s, g), s * WG_PER_SIGMA, 2 * g]
            onset = new_phase_onset.get(peak)
            zero = onset is not None and num < onset
            new_prev[peak] = prev[peak] if zero else dict(
                center=bv[f"v{k}_center"].value, amplitude=amp, sigma=s, gamma=g)
        row += [bv["bkg_slope"].value, bv["bkg_intercept"].value, rel, att]
        rows[num] = row
        if plot_every and len(rows) % plot_every == 0:
            plot_fit(th, In, out, f"num={num}  rel.res={rel:.3f}")
        return new_prev

    prev = {p: dict(v) for p, v in start.items()}
    for idx in reversed(range(0, t_idx + 1)):
        prev = do(idx, prev)
    prev = {p: dict(v) for p, v in start.items()}
    for idx in range(t_idx + 1, len(files)):
        prev = do(idx, prev)

    cols = ["num"]
    for peak in peaks:
        cols += [f"2th_{peak}", f"I_{peak}", f"FWHM_{peak}", f"wG_{peak}", f"wL_{peak}"]
    cols += ["bkgslope", "bkgint", "relres", "attempts"]
    df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=cols)
    for peak, onset in new_phase_onset.items():
        if peak in peaks:
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


def summary_plot(df):
    fig, ax = plt.subplots(4, 1, figsize=(7, 8), dpi=100, sharex=True)
    for peak in peaks:
        for a, col in zip(ax[:3], ["2th", "I", "FWHM"]):
            a.plot(df["num"], df[f"{col}_{peak}"], ".", ms=2, label=peak)
            a.set_ylabel(col)
    ax[3].plot(df["num"], df["relres"], ".", ms=2)
    ax[3].set_ylabel("relres")
    ax[0].legend()
    ax[-1].set_xlabel("num")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    in_dir = folder_path / bcg_folder_name
    files = sorted(os.listdir(in_dir), key=file_num)
    init_all = read_initial(folder_path / f"{specimen_name}_initial.xlsx")
    missing = [p for p in peaks if p not in init_all]
    if missing:
        raise ValueError(f"初期値ファイルに {missing} がありません")
    out_path = folder_path / f"{specimen_name}output.xlsx"
    refs = load_reference(out_path)
    df = run(files, in_dir, init_all, refs)
    save(df, out_path, "".join(peaks))
    summary_plot(df)
