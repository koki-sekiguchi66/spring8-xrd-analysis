import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

function fileProtocolCompatibleHtml(): Plugin {
  return {
    name: 'file-protocol-compatible-html',
    enforce: 'post',
    transformIndexHtml(html) {
      return html
        .replace(/<script type="module" crossorigin/g, '<script defer')
        .replace(/<script type="module"/g, '<script defer')
        .replace(/ crossorigin/g, '')
        .replace('</head>', '    <link rel="stylesheet" href="./assets/style.css" />\n  </head>');
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [react(), fileProtocolCompatibleHtml()],
  build: {
    chunkSizeWarningLimit: 6000,
    rollupOptions: {
      output: {
        format: 'iife',
        inlineDynamicImports: true,
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
});
