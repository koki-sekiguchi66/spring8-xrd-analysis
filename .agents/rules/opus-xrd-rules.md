# XRD AutoFit Studio - Workspace Development Rules (For Claude Opus in Antigravity)

## 1. 必読ドキュメントとアーキテクチャ遵守
- 実装を開始する前に、必ずルートディレクトリの implementation_plan.md を読み込み、記載された4フェーズの設計仕様・Origin完全互換Voigt数式・8項目のバグ修正仕様を厳密に遵守すること。
- 動作環境は Windows 11 ローカル完結（127.0.0.1 のみ）とし、外部サーバーへのデータ送信を一切行わないこと。

## 2. フロントエンドUI実装時の必須スキルチェーン（脱・AIチックUI）
フロントエンド（React + TypeScript + Tailwind CSS + shadcn/ui + Plotly.js）の画面・コンポーネントを作成・修正する際は、必ず .agents/skills/ 内の以下のスキルを順番に参照・適用すること：
1. **rontend-design / ui-ux-pro-max**:
   - 凡庸なAI生成テンプレート（白背景に紫グラデーション、Interフォント、均等すぎるカードグリッド）を厳禁とする。
   - 「精密科学計測・X線回折解析スタジオ」にふさわしいダークモード基調（Deep Slate / Zinc ベース、オーステナイト $\gamma＝シアン/ブルー系、マルテンサイト $\alpha'＝アンバー/オレンジ系の明確な機能色）と高視認性フォントペアリング（Geist Sans / JetBrains Mono 等）を採用すること。
2. **aseline-ui / ixing-motion-performance / ixing-accessibility**:
   - 回折角 \theta$、面積強度 $、半値幅 , w_L, \text{FWHM}$、残差などの数値表示には必ず **	abular-nums（等幅数字）** を適用し、リアルタイム更新時の桁ズレ・レイアウト揺れを防止すること。
   - h-screen ではなく h-dvh を使用し、トランジションは 150ms〜200ms 以内の軽快なコンポジターアニメーションに限定すること。
3. **eact-best-practices / composition-patterns / web-design-guidelines**:
   - 7,680点×複数波形のPlotly WebGL描画やWebSocket進捗ストリームにおいて不要な再レンダリングを防止し、Compound Componentsパターンで保守性の高いコードに保つこと。

## 3. バックエンド・Excel処理時の必須スキル
- （試料名）_initial.xlsx の自動生成および （試料名）output.xlsx へのシート出力・画像埋め込みを実装する際は、**xlsx** スキルおよび implementation_plan.md のカラム順序 [num, 2th, I, wG, wL, FWHM] を厳守すること。
