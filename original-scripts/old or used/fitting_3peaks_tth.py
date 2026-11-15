# peak fitting するプログラム

# Lmfitを仮想環境(今回はfitting1)にpip install する / matplotlib, pandas, openpyxlはconda install　
#https://qiita.com/mckeeeen/items/d4cbe4a16a102157f40c

#仮想環境(今回はfitting1)でspyderを開く
#https://work-life-enj.com/spyder-virtual-environment/

import matplotlib.pyplot as plt
import numpy as np
import os 
from lmfit import Model
from lmfit.models import VoigtModel
import math
import pandas as pd

#入力-----------------------------------------------------------------------------
# 処理したいファイルの入っているフォルダパス
in_path = 'L:\\SPring-8\\diffracion data\\Ga5C_90CR\\23-436\\'
#出力するファイルパス
out_path = 'L:\\SPring-8\\diffracion data\\CR90_output.xlsx'
#初期値（originでフィッテングした結果）の格納されたファイルパス
init_path = 'L:\\SPring-8\\diffracion data\\CR90_start_fcc111_bct011_bct110.xlsx'
#フィッテングする回折角2thetaの範囲の最小値
th_min = 11.0
#フィッテングする回折角2thetaの範囲の最大値
th_max = 12.0
#ピークの数
n = 3
#回折角の小さい順のピーク
peaks = ["fcc111", "bct110", "bct011"]
#--------------------------------------------------------------------------------

#初期値の読み込み
data_pd = pd.read_excel(init_path, usecols=[1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16, 17, 18], skiprows=[0]) # https://note.nkmk.me/python-pandas-read-excel/
data = data_pd.values # https://note.nkmk.me/python-pandas-numpy-conversion/

#初期値
Init_pars = {}
Init_pars['num'] = data[0][0]
Init_pars['v1_center'] = data[0][1]
Init_pars['v1_amplitude'] = data[0][2]
Init_pars['v1_sigma'] = data[0][3]/(2*math.sqrt(4*math.log(2, math.e)))
Init_pars['v1_gamma'] = data[0][4]/2
Init_pars['v2_center'] = data[0][5]
Init_pars['v2_amplitude'] = data[0][6]
Init_pars['v2_sigma'] = data[0][7]/(2*math.sqrt(4*math.log(2, math.e)))
Init_pars['v2_gamma'] = data[0][8]/2


#処理ファイルの名前リストと数
all_file = os.listdir(in_path) # https://webstation-plus.com/listdir.html
cont_all_file = len(all_file)


#出力データを格納する変数の定義
all_results = np.empty((1,1+n*3), float) # https://pyming.info/2022/02/10/numpy_empty/
cur_result = np.empty((1,1+n*3), float)


for i in range(0, cont_all_file):
    

    #処理したいファイルの読み込み
    in_file_path = in_path + all_file[i]
    in_file = np.loadtxt(in_file_path, dtype = 'float')
        
    # number of theta data 
    count_th = np.count_nonzero((in_file >= th_min) & (in_file <= th_max), axis=0)[0]
    
    #回折角thと強度Inをそれぞれ2次元配列に格納する変数の定義
    th = np.empty((1, count_th), float)
    In = np.empty((1, count_th), float)
    
    #回折角thと強度Inをそれぞれ2次元配列に格納
    u_th = 0
    for j in range(0, len(in_file)):
        if (in_file[j][0] >= th_min) and (in_file[j][0] <= th_max):
            th[0][u_th] = in_file[j][0]
            In[0][u_th] = in_file[j][1] 
            u_th += 1 

    #フィッテング開始
    voigt1 = VoigtModel(prefix='v1_')
    pars = voigt1.guess(In[0], x=th[0])
    pars['v1_center'].set(value=Init_pars["v1_center"], min=0)
    pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=0)
    pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=0)
    pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=0)
    
    for k in range(2, n+1):
        pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
        pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center'], min=0)
        pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude'], min=0)
        pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
        pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
    
    mod = voigt1
    for l in range(2, n+1):
        mod += VoigtModel(prefix='v' + str(l) + '_')
    
    init = mod.eval(pars, x=th[0])
    out = mod.fit(In[0], pars, x=th[0])
    comps = out.eval_components(x=th[0])
    #フィッテング終わり

    
    #パラメータの出力
    
    if i >=1: 
        #2回目以降で、もしフィッテングがうまくいっていなかったら、HCP002のIの初期値を上下させる。
        tmp_dict = {}
        # パラメータ要確認！!
        if (abs(out.best_values.get('v2_amplitude') - all_results[i-1][5]) >= 50) or (abs(out.best_values.get('v2_center') - all_results[i-1][4]) >= 0.01):
            for vib in range(-15, 3, 1):
                #パラメータ要確認！!
                vib_I = 2*vib
                #フィッテング開始
                voigt1 = VoigtModel(prefix='v1_')
                pars = voigt1.guess(In[0], x=th[0])
                pars['v1_center'].set(value=Init_pars["v1_center"], min=0)
                pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=0)
                pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=0)
                pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=0)
                
                for k in range(2, n+1):
                    pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
                    pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center'], min=0)
                    pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude']+vib_I, min=0)
                    pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
                    pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
                
                mod = voigt1
                for l in range(2, n+1):
                    mod += VoigtModel(prefix='v' + str(l) + '_')
                
                init = mod.eval(pars, x=th[0])
                out = mod.fit(In[0], pars, x=th[0])
                comps = out.eval_components(x=th[0])
                #フィッテング終わり
                #辞書にvibの値とHCP002の角度を格納
                tmp_dict[vib] = abs(out.best_values.get('v2_center') - all_results[i-1][4])
                
                """
                #vibration の結果の描画
                fig, ax = plt.subplots(2,1,dpi=130)
                ax=ax.ravel()
                
                ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].lstrip('suzu2_').rstrip("bcg.csv")) + "_vib=" + str(vib))
                ax[0].plot(th[0], out.best_fit, '-', label='best fit',zorder=10,lw=2)
                
            
                ax[1].plot(th[0], In[0], 'C6o',alpha=0.5)
                for p in range(1, n+1):
                    ax[1].plot(th[0], comps['v' + str(p) + '_'], 'C'+str(p)+'--', label='component'+str(p))

                ax[0].set(xlabel="2theta",ylabel="Intensity")
                ax[1].set(xlabel="2theta",ylabel="Intensity")
                ax[0].set_xlim(th_min, th_max)
                ax[0].set_ylim(-100, 50000)
                ax[0].set_xlim(th_min, th_max)
                ax[1].set_xlim(th_min, th_max)
                ax[1].set_ylim(-100, 20000)
                ax[0].legend(loc='best')
                ax[1].legend(loc='best')
                
                plt.show()
                print("vib", vib, "tmp_dict", tmp_dict)
                #vibration の結果の描画終わり
                """
                
            #最も前回の回折角の値との差が小さくなる場合のvib_Iをbest_Iとして、Iの初期値に加え、もう一度フィッテングする。
            best_I = min(tmp_dict, key=tmp_dict.get)*4
            best_th = 0

            """
            #最も良いIの初期値でthの初期値を動かす
            for v_th in range(-1, 2, 1):
                #パラメータ要確認！!
                vib_th = 0.005*v_th
                #フィッテング開始
                voigt1 = VoigtModel(prefix='v1_')
                pars = voigt1.guess(In[0], x=th[0])
                pars['v1_center'].set(value=Init_pars["v1_center"], min=0)
                pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=0)
                pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=0)
                pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=0)
                
                for k in range(2, n+1):
                    pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
                    pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center']+vib_th, min=0)
                    pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude']+best_I, min=0)
                    pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
                    pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
                
                mod = voigt1
                for l in range(2, n+1):
                    mod += VoigtModel(prefix='v' + str(l) + '_')
                
                init = mod.eval(pars, x=th[0])
                out = mod.fit(In[0], pars, x=th[0])
                comps = out.eval_components(x=th[0])
                #フィッテング終わり
                #辞書にvibの値とHCP002の角度を格納
                tmp_dict_th[v_th] = abs(out.best_values.get('v2_center') - all_results[i-1][4])
                
            best_th = min(tmp_dict_th, key=tmp_dict_th.get)*0.01    
            """

            #最もよい結果でフィッテング開始
            voigt1 = VoigtModel(prefix='v1_')
            pars = voigt1.guess(In[0], x=th[0])
            pars['v1_center'].set(value=Init_pars["v1_center"], min=0)
            pars['v1_amplitude'].set(value=Init_pars["v1_amplitude"], min=0)
            pars['v1_sigma'].set(value=Init_pars["v1_sigma"], min=0)
            pars['v1_gamma'].set(value=Init_pars["v1_gamma"], min=0)
            
            for k in range(2, n+1):
                pars.update(VoigtModel(prefix='v' + str(k) + '_').make_params())
                pars['v' + str(k) + '_'+'center'].set(value=Init_pars['v' + str(k) + '_'+'center']+best_th, min=0)
                pars['v' + str(k) + '_'+'amplitude'].set(value=Init_pars['v' + str(k) + '_'+'amplitude']+best_I, min=0)
                pars['v' + str(k) + '_'+'sigma'].set(value=Init_pars['v' + str(k) + '_'+'sigma'], min=0)
                pars['v' + str(k) + '_'+'gamma'].set(value=Init_pars['v' + str(k) + '_'+'gamma'], min=0)
            
            mod = voigt1
            for l in range(2, n+1):
                mod += VoigtModel(prefix='v' + str(l) + '_')
            
            init = mod.eval(pars, x=th[0])
            out = mod.fit(In[0], pars, x=th[0])
            comps = out.eval_components(x=th[0])
            #フィッテング終わり


            #vibration で得た最良の結果をall_resultsに格納
            cur_result[0][0] =  all_file[i].rstrip(".tth")[-4:]
            for m in range(1, n+1):
                cur_result[0][1+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'center')
                cur_result[0][2+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'amplitude')
                c = out.best_values.get('v' + str(m) + '_'+'sigma')
                d = out.best_values.get('v' + str(m) + '_'+'gamma')
                cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)
            all_results = np.append(all_results, cur_result, axis=0) # https://note.nkmk.me/python-pandas-to-excel/
            print("fitting repeated:", all_results[i][0])
                
            
            #フィッテングの結果描画
            fig, ax = plt.subplots(2,1,dpi=130)
            ax=ax.ravel()
            ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip(".tth")[-4:]))
            ax[0].plot(th[0], out.best_fit, '-', label='best fit',zorder=10,lw=2)
            ax[1].plot(th[0], In[0], 'C6o',alpha=0.5)
            for p in range(1, n+1):
                ax[1].plot(th[0], comps['v' + str(p) + '_'], 'C'+str(p)+'--', label='component'+str(p))
            ax[0].set(xlabel="2theta",ylabel="Intensity")
            ax[1].set(xlabel="2theta",ylabel="Intensity")
            ax[0].set_xlim(th_min, th_max)
            ax[0].set_ylim(-100, 50000)
            ax[0].set_xlim(th_min, th_max)
            ax[1].set_xlim(th_min, th_max)
            ax[1].set_ylim(-100, 20000)
            ax[0].legend(loc='best')
            ax[1].legend(loc='best')
            plt.show()
            #フィッテングの結果描画　終わり
            
            
        else:
            #2回目以降で、フィッテングがうまくいっていた場合、それまでの結果に追加
            cur_result[0][0] = all_file[i].rstrip(".tth")[-4:]
            for m in range(1, n+1):
                cur_result[0][1+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'center')
                cur_result[0][2+(m-1)*3] = out.best_values.get('v' + str(m) + '_'+'amplitude')
                c = out.best_values.get('v' + str(m) + '_'+'sigma')
                d = out.best_values.get('v' + str(m) + '_'+'gamma')
                cur_result[0][3+(m-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)
            all_results = np.append(all_results, cur_result, axis=0) # https://note.nkmk.me/python-pandas-to-excel/
            print("fitted:", all_results[i][0])
            
            
            #フィッテングの結果描画
            fig, ax = plt.subplots(2,1,dpi=130)
            ax=ax.ravel()
            ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip(".tth")[-4:]))
            ax[0].plot(th[0], out.best_fit, '-', label='best fit',zorder=10,lw=2)
            ax[1].plot(th[0], In[0], 'C6o',alpha=0.5)
            for p in range(1, n+1):
                ax[1].plot(th[0], comps['v' + str(p) + '_'], 'C'+str(p)+'--', label='component'+str(p))
            ax[0].set(xlabel="2theta",ylabel="Intensity")
            ax[1].set(xlabel="2theta",ylabel="Intensity")
            ax[0].set_xlim(th_min, th_max)
            ax[0].set_ylim(-100, 50000)
            ax[0].set_xlim(th_min, th_max)
            ax[1].set_xlim(th_min, th_max)
            ax[1].set_ylim(-100, 20000)
            ax[0].legend(loc='best')
            ax[1].legend(loc='best')
            plt.show()
            #フィッテングの結果描画　終わり
    
    
        #初めて結果を出力する場合、all_resultsのdefault値を変更
    elif i == 0:
        all_results[0][0] = all_file[i].rstrip(".tth")[-4:]
        for a in range(1, n+1):
            all_results[0][1+(a-1)*3] = out.best_values.get('v' + str(a) + '_'+'center')
            all_results[0][2+(a-1)*3] = out.best_values.get('v' + str(a) + '_'+'amplitude')
            c = out.best_values.get('v' + str(a) + '_'+'sigma')
            d = out.best_values.get('v' + str(a) + '_'+'gamma')
        all_results[0][3+(a-1)*3] = 1.0692*d+math.sqrt(0.8664*d**2+5.545083*c**2)
        print("fitted:", Init_pars['num'])
        
        
        #フィッテングの結果描画
        fig, ax = plt.subplots(2,1,dpi=130)
        ax=ax.ravel()
        ax[0].plot(th[0], In[0], 'o', label=str(all_file[i].rstrip(".tth")[-4:]))
        ax[0].plot(th[0], out.best_fit, '-', label='best fit',zorder=10,lw=2)
        ax[1].plot(th[0], In[0], 'C6o',alpha=0.5)
        for p in range(1, n+1):
            ax[1].plot(th[0], comps['v' + str(p) + '_'], 'C'+str(p)+'--', label='component'+str(p))
        ax[0].set(xlabel="2theta",ylabel="Intensity")
        ax[1].set(xlabel="2theta",ylabel="Intensity")
        ax[0].set_xlim(th_min, th_max)
        ax[0].set_ylim(-100, 50000)
        ax[0].set_xlim(th_min, th_max)
        ax[1].set_xlim(th_min, th_max)
        ax[1].set_ylim(-100, 2000)
        ax[0].legend(loc='best')
        ax[1].legend(loc='best')
        plt.show()
        #フィッテングの結果描画　終わり
 

#外部ファイルに出力
col = ['num', '2th_'+ peaks[0], 'I_'+ peaks[0], 'FWHM_'+ peaks[0], '2th_'+ peaks[1], 'I_'+ peaks[1], 'FWHM_'+ peaks[1]]
df = pd.DataFrame(all_results, columns=col) # https://note.nkmk.me/python-pandas-to-excel/

with pd.ExcelWriter(out_path, engine="openpyxl", mode='a', if_sheet_exists='new') as writer:
    df.to_excel(writer, sheet_name='Results', index=False)


#パラメータの描画
fig, ax = plt.subplots(3*n,1,dpi=130)
ax=ax.ravel()

for i in range(0, n):
    ax[0+i*3].plot(df["num"], df[col[1+i*3]], '.', label=col[1+i*3]) # https://pythondatascience.plavox.info/pandas/%E8%A1%8C%E3%83%BB%E5%88%97%E3%81%AE%E6%8A%BD%E5%87%BA
    ax[1+i*3].plot(df["num"], df[col[2+i*3]], '.', label=col[2+i*3])
    ax[2+i*3].plot(df["num"], df[col[3+i*3]], '.', label=col[3+i*3]) 

    ax[0+i*3].legend()
    ax[1+i*3].legend()
    ax[2+i*3].legend()
  
plt.show()
