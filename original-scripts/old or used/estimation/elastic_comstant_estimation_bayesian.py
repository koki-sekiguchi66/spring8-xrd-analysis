# -*- coding: utf-8 -*-
"""
Created on Wed Dec 24 14:46:52 2025

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

# 2. データの標準化 (Standardization)
# モデルが学習しやすいように平均0、分散1に変換します
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)

# 3. モデルの学習 (各特性ごと)
gp_models = {}
for target in targets:
    y = df[target].values
    # 標準化により、length_scaleの初期値や範囲が扱いやすくなります
    kernel = C_kern(1.0, (1e-3, 1e3)) * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e2))
    gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=15, alpha=1e-5)
    gp.fit(X_scaled, y)
    gp_models[target] = gp
    print(f"Finished training for {target}. Optimized Kernel: {gp.kernel_}")

# 4. ヒートマップ用の予測 (グリッド作成)
ni_range = np.linspace(12, 35, 100)
c_range = np.linspace(0, 1.0, 100)
NI_grid, C_grid = np.meshgrid(ni_range, c_range)
X_test_raw = np.column_stack([NI_grid.ravel(), C_grid.ravel()])

# 重要：予測用データも同じスケーラーで変換する
X_test_scaled = scaler.transform(X_test_raw)

# 描画準備
fig, axes = plt.subplots(1, 3, figsize=(20, 5.5))

for i, target in enumerate(targets):
    y_pred = gp_models[target].predict(X_test_scaled).reshape(NI_grid.shape)
    
    # ヒートマップ描画 (等高線塗りつぶし)
    im = axes[i].contourf(C_grid, NI_grid, y_pred, levels=50, cmap='RdYlBu_r')
    axes[i].set_title(f'Predicted {target} Map', fontsize=14)
    axes[i].set_xlabel('C content (wt%)', fontsize=12)
    axes[i].set_ylabel('Ni content (wt%)', fontsize=12)
    
    # 元のデータ点をプロットして分布を確認
    axes[i].scatter(df['C'], df['Ni'], c='black', s=15, alpha=0.6, label='Exp. Data')
    fig.colorbar(im, ax=axes[i], label=f'{target}')

plt.tight_layout()
plt.show()

# 5. Ni=24 wt% 固定の予測と可視化
c_plot = np.linspace(0, 1.0, 101)
X_fix_raw = np.column_stack([np.full_like(c_plot, 24.0), c_plot])
X_fix_scaled = scaler.transform(X_fix_raw)

plt.figure(figsize=(9, 6))
for target in targets:
    y_p, sigma = gp_models[target].predict(X_fix_scaled, return_std=True)
    plt.plot(c_plot, y_p, label=f'{target} prediction', lw=2)
    plt.fill_between(c_plot, y_p - 2*sigma, y_p + 2*sigma, alpha=0.15) # 95%信頼区間

plt.title('Prediction at Ni = 24.0 wt% (Bayesian GP)', fontsize=14)
plt.xlabel('C content (wt%)', fontsize=12)
plt.ylabel('Elastic Constant', fontsize=12)
plt.legend()
plt.grid(alpha=0.3)
plt.show()