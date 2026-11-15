# -*- coding: utf-8 -*-
"""
Created on Wed Dec 24 15:37:32 2025

@author: harad
"""

import numpy as np
import pandas as pd
import io
import matplotlib.pyplot as plt
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C_kern

# --- 1. データ読み込み ---
data_input = """
Ni	C	c11	c12	C44
34.41	0	1.3328	0.857	1.0591
30.03	0	1.5258	0.9157	1.1313
28.21	0	1.608	0.9578	1.1598
29.96	0.12	1.5433	0.9387	1.1262
27.58	0.2	1.6028	0.9527	1.1571
29.18	0.26	1.4795	0.8829	1.1076
28.15	0.26	1.5801	0.9354	1.1354
25.11	0.32	1.7905	1.095	1.1571
22.45	0.38	1.9091	1.1921	1.1708
27.78	0.51	1.5516	0.9167	1.1051
30.11	0.54	1.4196	0.8483	1.0707
25.3	0.54	1.7964	1.1068	1.1309
22.48	0.55	1.8824	1.1732	1.1535
20.23	0.63	1.9472	1.2156	1.1563
27.7	0.64	1.5331	0.8967	1.0817
24.35	0.65	1.7487	1.0615	1.1101
19.95	0.68	1.9384	1.2059	1.1511
29.65	0.7	1.3933	0.8387	1.0406
22.5	0.7	1.8675	1.1555	1.1256
19.95	0.83	1.9388	1.2125	1.128
29.86	0.87	1.4053	0.8553	1.0308
24.87	0.88	1.655	0.9721	1.0905
15.11	0.9	2.0576	1.2507	1.1538
15.1	0.92	2.0579	1.2502	1.1479
22.58	0.95	1.8428	1.1392	1.0954
17.15	0.96	2.0021	1.2326	1.1281
12.33	0.96	2.1477	1.3148	1.1603
15.02	1	2.0467	1.2401	1.135


"""
df = pd.read_csv(io.StringIO(data_input.strip()), sep='\t')
X_raw = df[['Ni', 'C']].values
targets = ['c11', 'c12', 'C44']

# --- 2. モデル構築 ---

# A. 多項式回帰 (Polynomial) - 生データを使用
poly = PolynomialFeatures(degree=1)
X_poly = poly.fit_transform(X_raw)
poly_models = {}
for t in targets:
    poly_models[t] = LinearRegression().fit(X_poly, df[t].values)

# B. ベイズ推定 (Gaussian Process) - 標準化データを使用
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)
gp_models = {}
for t in targets:
    # 上限を 1e6 (1,000,000) まで引き上げる
    kernel = C_kern(1.0, (1e-3, 1e3)) * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e6))
    gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=10, alpha=0.01)
    gp.fit(X_scaled, df[t].values)
    gp_models[t] = gp

# --- 3. 特定のポイントでの数値予測出力 ---
test_points = np.array([[24.0, 0.3], [24.0, 0.5], [24.0, 0.6], [24.0, 0.8], [24.0, 1.0]])
test_points_poly = poly.transform(test_points)
test_points_scaled = scaler.transform(test_points)

print("=== 予測結果比較 (Ni=24.0 wt%) ===")
print(f"{'C (wt%)':<8} | {'Prop':<5} | {'Poly Value':<10} | {'Bayes Value':<10} | {'Uncertainty(σ)':<15}")
print("-" * 65)

for i, p_raw in enumerate(test_points):
    c_val = p_raw[1]
    for t in targets:
        # 多項式予測
        val_poly = poly_models[t].predict(test_points_poly[i].reshape(1, -1))[0]
        # ベイズ予測
        val_gp, sigma = gp_models[t].predict(test_points_scaled[i].reshape(1, -1), return_std=True)
        
        print(f"{c_val:<8.1f} | {t:<5} | {val_poly:<10.4f} | {val_gp[0]:<10.4f} | {sigma[0]:<15.4f}")
    print("-" * 65)


# --- 4. グラフ作成 1: Ni=24固定での比較プロット ---
c_range = np.linspace(0, 1.0, 100)
X_line_raw = np.column_stack([np.full_like(c_range, 24.0), c_range])

X_line_poly = poly.transform(X_line_raw)
X_line_scaled = scaler.transform(X_line_raw)

fig1, axes1 = plt.subplots(1, 3, figsize=(18, 5))
fig1.suptitle('Prediction Comparison at Ni = 24.0 wt%', fontsize=16)

for i, t in enumerate(targets):
    # 多項式プロット
    y_poly = poly_models[t].predict(X_line_poly)
    axes1[i].plot(c_range, y_poly, 'b--', label='Polynomial (deg=2)', linewidth=2)
    
    # ベイズプロット
    y_gp, sigma = gp_models[t].predict(X_line_scaled, return_std=True)
    axes1[i].plot(c_range, y_gp, 'r-', label='Bayesian GP', linewidth=2)
    axes1[i].fill_between(c_range, y_gp - sigma, y_gp + sigma, color='r', alpha=0.2, label='GP Uncertainty (±1σ)')
    
    axes1[i].set_title(t)
    axes1[i].set_xlabel('C content (wt%)')
    axes1[i].set_ylabel('Elastic Constant')
    axes1[i].legend()
    axes1[i].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# --- 5. グラフ作成 2: ヒートマップ比較 (上段:多項式, 下段:ベイズ) ---
ni_grid = np.linspace(12, 35, 50)
c_grid = np.linspace(0, 1.0, 50)
NI, C_mesh = np.meshgrid(ni_grid, c_grid)
X_grid_raw = np.column_stack([NI.ravel(), C_mesh.ravel()])

X_grid_poly = poly.transform(X_grid_raw)
X_grid_scaled = scaler.transform(X_grid_raw)

fig2, axes2 = plt.subplots(2, 3, figsize=(18, 10))
fig2.suptitle('Heatmap Comparison: Polynomial vs Bayesian GP', fontsize=16)

# 共通の設定
levels = 20
cmap = 'viridis'

for i, t in enumerate(targets):
    # 多項式ヒートマップ
    Z_poly = poly_models[t].predict(X_grid_poly).reshape(NI.shape)
    im1 = axes2[0, i].contourf(C_mesh, NI, Z_poly, levels=levels, cmap=cmap)
    axes2[0, i].set_title(f'Polynomial: {t}')
    axes2[0, i].scatter(df['C'], df['Ni'], c='white', s=10, alpha=0.5) # データ点
    fig2.colorbar(im1, ax=axes2[0, i])
    
    # ベイズヒートマップ
    Z_gp = gp_models[t].predict(X_grid_scaled).reshape(NI.shape)
    im2 = axes2[1, i].contourf(C_mesh, NI, Z_gp, levels=levels, cmap=cmap)
    axes2[1, i].set_title(f'Bayesian GP: {t}')
    axes2[1, i].scatter(df['C'], df['Ni'], c='white', s=10, alpha=0.5) # データ点
    fig2.colorbar(im2, ax=axes2[1, i])

    # 軸ラベル（下段のみ）
    if i == 0:
        axes2[0, 0].set_ylabel('Ni (wt%)')
        axes2[1, 0].set_ylabel('Ni (wt%)')
    axes2[1, i].set_xlabel('C (wt%)')

plt.tight_layout()
plt.show()