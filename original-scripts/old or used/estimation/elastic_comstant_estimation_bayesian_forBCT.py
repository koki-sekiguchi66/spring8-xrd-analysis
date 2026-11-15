# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 13:18:27 2026

@author: harad
"""

import numpy as np
import pandas as pd
import io
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
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

# 【修正1】sep='\s+' に変更して、タブとスペースの両方に対応させる
df = pd.read_csv(io.StringIO(data_input.strip()), sep='\s+')

X_raw = df[['Ni', 'C']].values
targets = ['c11', 'c12', 'c44', 'c33', 'c13', 'c66']

# 2. データの標準化
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)

# 3. モデルの学習
gp_models = {}
for target in targets:
    y = df[target].values
    # 警告対策で上限を少し緩めています (1e2 -> 1e5)
    kernel = C_kern(1.0, (1e-3, 1e3)) * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e5))
    gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=15, alpha=1e-5)
    gp.fit(X_scaled, y)
    gp_models[target] = gp
    print(f"Finished training for {target}.")

# 4. ヒートマップ用の予測
# 【修正2】範囲をデータに合わせて拡大 (Ni: 0〜40)
ni_range = np.linspace(0, 40, 100) 
c_range = np.linspace(0, 1.5, 100) # Cも少し広めに
NI_grid, C_grid = np.meshgrid(ni_range, c_range)
X_test_raw = np.column_stack([NI_grid.ravel(), C_grid.ravel()])

X_test_scaled = scaler.transform(X_test_raw)

# 【修正3】6つのターゲットに合わせて 2行3列 (2, 3) に変更
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
axes_flat = axes.flatten() # ループしやすいように平坦化

for i, target in enumerate(targets):
    y_pred = gp_models[target].predict(X_test_scaled).reshape(NI_grid.shape)
    
    ax = axes_flat[i]
    im = ax.contourf(C_grid, NI_grid, y_pred, levels=50, cmap='RdYlBu_r')
    ax.set_title(f'{target}', fontsize=14)
    ax.set_xlabel('C (wt%)', fontsize=10)
    ax.set_ylabel('Ni (wt%)', fontsize=10)
    
    # 元データをプロット
    ax.scatter(df['C'], df['Ni'], c='black', s=20, edgecolors='white', label='Data')
    fig.colorbar(im, ax=ax)

plt.tight_layout()
plt.show()

# 5. Ni=24 wt% 固定の予測
c_plot = np.linspace(0, 1.5, 101)
X_fix_raw = np.column_stack([np.full_like(c_plot, 24.0), c_plot])
X_fix_scaled = scaler.transform(X_fix_raw)

plt.figure(figsize=(10, 6))
# 色を区別しやすいようにカラーマップを使用
colors = plt.cm.tab10(np.linspace(0, 1, len(targets)))

for i, target in enumerate(targets):
    y_p, sigma = gp_models[target].predict(X_fix_scaled, return_std=True)
    plt.plot(c_plot, y_p, label=f'{target}', lw=2, color=colors[i])
    plt.fill_between(c_plot, y_p - sigma, y_p + sigma, color=colors[i], alpha=0.1)

plt.title('Predicted Elastic Constants at Ni = 24.0 wt%', fontsize=14)
plt.xlabel('C content (wt%)', fontsize=12)
plt.ylabel('Elastic Constant (GPa)', fontsize=12)
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left') # 凡例を枠外へ
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()