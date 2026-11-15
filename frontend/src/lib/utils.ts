import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

declare global {
  interface Window {
    pywebview?: {
      api?: {
        api_get: <T>(url: string) => Promise<T>;
        api_post: <T>(url: string, body: unknown) => Promise<T>;
        start_fitting_stream: (payload: unknown) => Promise<{ status: string }>;
        start_video_export_stream: (payload: unknown) => Promise<{ status: string }>;
      };
    };
    __onDesktopFittingEvent?: (msg: any) => void;
    __onDesktopVideoEvent?: (msg: any) => void;
  }
}

export function isDesktopBridge(): boolean {
  return typeof window !== 'undefined' && Boolean(window.pywebview?.api);
}

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function fmtFixed(value: number | undefined | null, digits = 4): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '—';
  }
  return Number(value).toFixed(digits);
}

export function fmtSci(value: number | undefined | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value) || value <= 0) {
    return '—';
  }
  return Number(value).toExponential(digits);
}

export function getWsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host || '127.0.0.1:8000';
  return `${proto}//${host}${path}`;
}

export async function apiPost<T>(url: string, body: unknown): Promise<T> {
  if (isDesktopBridge() && window.pywebview?.api) {
    return window.pywebview.api.api_post<T>(url, body);
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      detail = errJson.detail || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(url: string): Promise<T> {
  if (isDesktopBridge() && window.pywebview?.api) {
    return window.pywebview.api.api_get<T>(url);
  }
  const res = await fetch(url);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      detail = errJson.detail || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function runFittingStream(
  payload: unknown,
  onMessage: (msg: any) => void
): Promise<void> {
  if (isDesktopBridge() && window.pywebview?.api) {
    return new Promise<void>((resolve, reject) => {
      window.__onDesktopFittingEvent = (msg: any) => {
        try {
          onMessage(msg);
          if (msg.type === 'all_complete') {
            resolve();
          } else if (msg.type === 'error') {
            reject(new Error(msg.detail || '連続フィッティング中にエラーが発生しました'));
          }
        } catch (e) {
          reject(e);
        }
      };
      window.pywebview!.api!.start_fitting_stream(payload).catch(reject);
    });
  }

  return new Promise<void>((resolve, reject) => {
    const ws = new WebSocket(getWsUrl('/ws/fitting/run'));
    ws.onopen = () => {
      ws.send(JSON.stringify(payload));
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        onMessage(msg);
        if (msg.type === 'all_complete') {
          ws.close();
          resolve();
        } else if (msg.type === 'error') {
          ws.close();
          reject(new Error(msg.detail || '連続フィッティング中にエラーが発生しました'));
        }
      } catch (e) {
        reject(e);
      }
    };
    ws.onerror = async () => {
      try {
        const syncRes = await apiPost<any>('/api/fitting/run', payload);
        onMessage({
          type: 'all_complete',
          groups: syncRes.groups,
        });
        resolve();
      } catch (fallbackErr) {
        reject(fallbackErr);
      }
    };
  });
}

export async function runVideoExportStream(
  payload: unknown,
  onMessage: (msg: any) => void
): Promise<void> {
  if (isDesktopBridge() && window.pywebview?.api) {
    return new Promise<void>((resolve, reject) => {
      window.__onDesktopVideoEvent = (msg: any) => {
        try {
          onMessage(msg);
          if (msg.type === 'complete') {
            resolve();
          } else if (msg.type === 'error') {
            reject(new Error(msg.detail || '動画フレーム切り出し中にエラーが発生しました'));
          }
        } catch (e) {
          reject(e);
        }
      };
      window.pywebview!.api!.start_video_export_stream(payload).catch(reject);
    });
  }

  return new Promise<void>((resolve, reject) => {
    const ws = new WebSocket(getWsUrl('/ws/video/export'));
    ws.onopen = () => {
      ws.send(JSON.stringify(payload));
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        onMessage(msg);
        if (msg.type === 'complete') {
          ws.close();
          resolve();
        } else if (msg.type === 'error') {
          ws.close();
          reject(new Error(msg.detail || '動画フレーム切り出し中にエラーが発生しました'));
        }
      } catch (e) {
        reject(e);
      }
    };
    ws.onerror = async () => {
      try {
        const syncRes = await apiPost<any>('/api/video/export', payload);
        onMessage({
          type: 'complete',
          ...syncRes,
        });
        resolve();
      } catch (fallbackErr) {
        reject(fallbackErr);
      }
    };
  });
}
