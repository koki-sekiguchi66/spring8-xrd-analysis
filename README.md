# XRD AutoFit Studio & DIC Utility (SPring-8 In-situ Edition)

準安定オーステナイト鋼（$\gamma$-FCC相 ＋ $\alpha'$-BCC相）のIn-situ X線回折（XRD）全自動連続解析・材料物理評価スタジオと、デジタル画像相関法（DIC）用 動画フレーム高速切り出しツールを統合した**完全ローカル・ネイティブデスクトップアプリケーション（Zero-Localhost / PyWebView IPC）**です。

---

## ワンクリック起動方法（Windows 11 / Localhost不要のネイティブ起動）

プロジェクトルートにある **[`run_app.bat`](file:///c:/Users/sekig/apps/spring8-xrd-analysis/run_app.bat)** をダブルクリックしてください。
**HTTPサーバー（`localhost` / TCPポート）を一切立ち上げず**、`frontend/dist/index.html` を直接ネイティブウィンドウ（PyWebView `file://` + インプロセスPython-JSブリッジ `DesktopBridge`）で起動します。

コマンドラインから起動する場合：
```powershell
# ネイティブデスクトップウィンドウモード（デフォルト・Localhostサーバーなし）
.\.venv\Scripts\python.exe backend\main.py

# オプション: 開発・テスト用Webサーバーモード (http://127.0.0.1:8000)
.\.venv\Scripts\python.exe backend\main.py --server --host 127.0.0.1 --port 8000
```

---

## 主要機能

### Mode 1: In-situ XRD AutoFit Studio（5ステップ・ウィザード ＋ 初心者ナビゲーション搭載）
すべてのステップの上部に**初心者向けインタラクティブ・チュートリアルガイド（`STEP 1 → STEP 2 → STEP 3` ＆ 専門用語ワンクリック解説）**を搭載し、画面遷移（サブスクリーン切替タブ）と大きな文字サイズ（16pxベース）により一画面がごちゃつかない洗練されたUIを実現しています。

1. **Step 1: フォルダ仕分け & バックグラウンド除去 (`separator.py` / `bg_remover.py`)**
   - `.tth` ファイルを `tth/` へ、その他を `others/` へ自動仕分け（50ファイル未満スキップ制限を撤廃し、冪等性を保証）。
   - スパイクノイズ除去 ＋ 下側凸包（Rubberband法）＋ 単調減少フィルタ ＋ PCHIP補間（およびarPLSフォールバック）による高精度バックグラウンド除去。
2. **Step 2: Origin完全互換Voigt初期値探索 & 面指数自動同定 (`origin_voigt.py` / `initial_guesser.py`)**
   - 「① 候補カードの選択画面」と「② 拡大波形・パラメータ微調整画面」を画面遷移で分離し、視認性を最大化。
   - 変形初期代表ファイル（`num=50` 等、$\gamma$-FCC単相）と変形後期代表ファイル（`num=900` 等、$\gamma+\alpha'$二相）を自動選出し、複数ファイルで同時に初期値フィッティングを実行。
   - $\gamma$-FCC（`fcc111`, `fcc200`, `fcc220`, `fcc311`, `fcc222`）および $\alpha'$-BCC（`bcc110`, `bcc200`, `bcc211`, `bcc220`）の9回折ピークを結晶学的に自動同定し、単一ピーク候補と重畳ペア候補（`fcc111 + bcc110`、`fcc222 + bcc220` 等）に自動分類。
   - 承認した初期値群から既存スクリプト完全互換の2段ヘッダーExcel `（試料名）_initial.xlsx` を自動生成。
3. **Step 3: 連続フィッティング実行 (`fitters/`)**
   - 「① エンジン＆拘束条件設定」と「② リアルタイム波形＆推移モニター」をサブ画面遷移で切り替え可能。
   - **1Peak** (`single_fitter.py`)、**2PeaksRatio** (`ratio2_fitter.py`)、**3PeaksLuders** (`luders3_fitter.py`)、**MultiPeaks** (`multi_fitter.py`) の4エンジンを搭載。各エンジンは原田さんの元スクリプト（1Peak=ver7.0、MultiPeaks=ver4.0.0、2PeaksRatio=ver10、3PeaksLuders=ver4）の解析手法・既定値に準拠し、論理バグのみ修正しています。
   - 背景は前処理でのみ除去し、フィット窓では Voigt 成分だけを当てはめます（元スクリプトどおり）。
   - 2PeaksRatio は冷間圧延材の既存 α' 用（変態開始前のみ、R を粗→細探索）、3PeaksLuders は同じく変態開始後用です。焼鈍・時効材の fcc111+bcc110 は MultiPeaks（新生ピーク）が既定です。
   - 初期値ファイル `init_num` から変形後期側（昇順）と変形初期側（降順）の双方向へパラメータを引き継ぎながら連続解析。
4. **Step 4: 各相の要確認フィット（外れ値）一括選択・個別/スマート再フィット & Excel出力 (`Step4ReviewExport.tsx` / `excel_io.py`)**
   - **複数相・全グループ横断の要確認フィット一括選択**: 連続フィッティング完了後、$\gamma$-FCC相および$\alpha'$-BCC相のすべての「要確認フィット（`outlier_nums`）」を一覧表示。「すべて一括選択」「$\gamma$-FCC相を一括選択」「$\alpha'$-BCC相を一括選択」または任意の `num` 追加が可能。
   - **選択項目の連続個別フィット（キュー送り `◀ 前の選択項目 / 次の選択項目 ▶`）** ＆ **ワンクリック「選択項目をスマート一括自動再フィット」**（前後正常フレームからの線形補間初期値＋拘束緩和による一括修復 `POST /api/fitting/refit-batch`）の両方に対応。
   - ピーク別シート・物理特性解析シート（`Physical_Analysis`）およびトレンドグラフ画像を埋め込んだ `（試料名）output.xlsx` を一括出力。
5. **Step 5: マルテンサイト相分率・各相転位密度・格子ひずみ解析ダッシュボード (`Step5PhysicsAnalysis.tsx` / `physics_analyzer.py`)**
   - Step 3〜4の解析結果（または既存の `*output.xlsx` ファイルの直接読み込み）から以下の材料物理量を自動算出・可視化：
     - **① マルテンサイト相分率 ($f_{\alpha'}$) & オーステナイト相分率 ($f_\gamma$) 推移**: 直接比較法（多重度 $p_{hkl}$・構造因子 $|F|^2/V_c^2$（Cromer-Mann 散乱因子・実測格子定数）・LP 因子・Debye-Waller 因子）による体積分率算出。使用する反射は選択可能（集合組織の強い fcc111 等を除外可）、同一反射の成分は合算、変態開始前の新生 α' は 0 とみなします。X線波長は入力値を使用します（既定 0.04133 nm）。参考として num に対する経験式 $f_{\alpha'} = f_s [1 - \exp(-\beta \max(0, \text{num}-\text{num}_0)^n)]$ をフィットします（ひずみ基準の Olson-Cohen 式ではありません）。
     - **② 各相（$\gamma$-FCC / $\alpha'$-BCC）の転位密度変化 ($\rho_\gamma, \rho_{\alpha'}$ [$\text{m}^{-2}$])**: Modified Williamson-Hall法（$\rho = 2\,\text{slope}^2/(\pi M^2 b^2)$、弾性異方性コントラスト因子 $\bar{C}_{hkl} = \bar{C}_{h00}(1 - q H^2)$ 考慮、半定量）および各結晶面ごとの転位密度推移（サイズ広がりを無視した上限値）、ならびに指定フレームの Modified W-H 線形回帰プロット（$\Delta K$ vs $K\sqrt{\bar{C}}$）。
     - **③ 弾性格子ひずみ ($\varepsilon_{hkl}$ [$\mu\varepsilon$]) & 格子定数 ($a_\gamma, a_{\alpha'}$ [$\text{nm}$]) の変化**: $\gamma$-FCC / $\alpha'$-BCC 相間の応力分配挙動の可視化。

### Mode 2: DIC Video Frame Extractor (`video_exporter.py` / `VideoUtilityTab.tsx`)
- 初心者向けステップナビゲーション＆DIC用語解説を搭載。
- **単一動画モード**（`export_video_to_image.py` 相当）および **フォルダ内全動画一括処理モード**（`export_videos_to_images.py` 相当）を統合。
- 大文字 `.MP4` / 小文字 `.mp4` / `.mov` / `.avi` を `Path.suffix.lower()` で確実に認識。
- `cv2.imencode()` ＋ `Path.write_bytes()` により、Windowsの日本語フォルダパス・ファイル名でも文字化けや保存失敗を起こさず高速出力。
