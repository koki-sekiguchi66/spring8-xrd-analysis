# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 13:22:51 2026

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

# 1. データの準備
data_input = """
Ni	C	c11	c12	c44 c33 c13 c66
0	0	231	135	117	231	135	117
0	0.819589171	230	140	115	180	130	115
0	0.454786104	238	139	116	190	130	116
0	1.413581017	229	145	115	160	135	113
0	0	231	135	117	231	135	117
24.8	0	190	135	115	190	135	115
32	0	150	125	105	150	125	105
36	0	130.6	127.8	88.5	130.6	127.8	88.5
"""

# sep='\s+' でタブとスペース混在に対応
df = pd.read_csv(io.StringIO(data_input.strip()), sep='\s+')

X_raw = df[['Ni', 'C']].values
targets = ['c11', 'c12', 'c44', 'c33', 'c13', 'c66']

# --- 2. モデル構築 ---

# A. 多項式回帰 (Polynomial)
# 【修正】degree=1 だと直線になります。ラベルに合わせて degree=2 (2次曲面) に修正しました。
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X_raw)
poly_models = {}
for t in targets:
    poly_models[t] = LinearRegression().fit(X_poly, df[t].values)

# B. ベイズ推定 (Gaussian Process)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)
gp_models = {}
for t in targets:
    # カーネル上限設定
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

# 2行3列のグラフを作成
fig1, axes1 = plt.subplots(2, 3, figsize=(18, 10))
fig1.suptitle('Prediction Comparison at Ni = 24.0 wt%', fontsize=16)
axes1_flat = axes1.flatten() # 【修正】ループしやすいように平坦化

for i, t in enumerate(targets):
    ax = axes1_flat[i]
    
    # 多項式プロット
    y_poly = poly_models[t].predict(X_line_poly)
    ax.plot(c_range, y_poly, 'b--', label='Polynomial (deg=2)', linewidth=2)
    
    # ベイズプロット
    y_gp, sigma = gp_models[t].predict(X_line_scaled, return_std=True)
    ax.plot(c_range, y_gp, 'r-', label='Bayesian GP', linewidth=2)
    ax.fill_between(c_range, y_gp - sigma, y_gp + sigma, color='r', alpha=0.2, label='GP Uncertainty (±1σ)')
    
    ax.set_title(t, fontsize=14)
    ax.set_xlabel('C content (wt%)')
    ax.set_ylabel('Elastic Constant')
    ax.grid(True, alpha=0.3)
    
    # 凡例は最初のグラフにだけ表示（見やすくするため）
    if i == 0:
        ax.legend(loc='upper right')

plt.tight_layout()
plt.show()

# --- 5. グラフ作成 2: ヒートマップ ---
# グリッド作成
ni_grid = np.linspace(0, 40, 50) # Ni範囲を0-40に拡大
c_grid = np.linspace(0, 1.5, 50) # C範囲を0-1.5に拡大
NI, C_mesh = np.meshgrid(ni_grid, c_grid)
X_grid_raw = np.column_stack([NI.ravel(), C_mesh.ravel()])

X_grid_poly = poly.transform(X_grid_raw)
X_grid_scaled = scaler.transform(X_grid_raw)

# 【修正】多項式とベイズを別の図として出力（混雑回避）

# --- Figure 2: 多項式回帰のヒートマップ ---
fig2, axes2 = plt.subplots(2, 3, figsize=(18, 10))
fig2.suptitle('Heatmap: Polynomial Regression (deg=2)', fontsize=16)
axes2_flat = axes2.flatten()

for i, t in enumerate(targets):
    ax = axes2_flat[i]
    Z_poly = poly_models[t].predict(X_grid_poly).reshape(NI.shape)
    
    im = ax.contourf(C_mesh, NI, Z_poly, levels=50, cmap='viridis')
    ax.set_title(f'Poly: {t}', fontsize=14)
    ax.set_xlabel('C (wt%)')
    ax.set_ylabel('Ni (wt%)')
    ax.scatter(df['C'], df['Ni'], c='white', s=20, edgecolors='black', label='Data')
    fig2.colorbar(im, ax=ax)

plt.tight_layout()
plt.show()

# --- Figure 3: ベイズ推定のヒートマップ ---
fig3, axes3 = plt.subplots(2, 3, figsize=(18, 10))
fig3.suptitle('Heatmap: Bayesian Gaussian Process', fontsize=16)
axes3_flat = axes3.flatten()

for i, t in enumerate(targets):
    ax = axes3_flat[i]
    Z_gp = gp_models[t].predict(X_grid_scaled).reshape(NI.shape)
    
    im = ax.contourf(C_mesh, NI, Z_gp, levels=50, cmap='RdYlBu_r') # ベイズは見やすい配色に変更
    ax.set_title(f'Bayes GP: {t}', fontsize=14)
    ax.set_xlabel('C (wt%)')
    ax.set_ylabel('Ni (wt%)')
    ax.scatter(df['C'], df['Ni'], c='black', s=20, edgecolors='white', label='Data')
    fig3.colorbar(im, ax=ax)

plt.tight_layout()
plt.show()