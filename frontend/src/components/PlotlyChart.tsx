import React, { useEffect, useRef } from 'react';
// @ts-expect-error plotly.js-dist-min does not ship bundled types
import Plotly from 'plotly.js-dist-min';

export interface PlotlyChartProps {
  data: Record<string, unknown>[];
  layout?: Record<string, unknown>;
  config?: Record<string, unknown>;
  className?: string;
  onPointClick?: (point: { x: number; y: number; curveNumber: number; pointIndex: number }) => void;
  onRangeSelect?: (rangeMin: number, rangeMax: number) => void;
}

const BASE_DARK_LAYOUT: Record<string, unknown> = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: '#0a0b0e',
  font: {
    family: '"Segoe UI", "Yu Gothic UI", system-ui, sans-serif',
    color: '#d4d8e0',
    size: 12,
  },
  margin: { l: 58, r: 18, t: 24, b: 44 },
  xaxis: {
    gridcolor: '#181b22',
    zerolinecolor: '#23262e',
    linecolor: '#23262e',
    tickfont: { family: '"Cascadia Mono", "JetBrains Mono", monospace', size: 11, color: '#9ca3b0' },
    titlefont: { size: 12, color: '#d4d8e0' },
  },
  yaxis: {
    gridcolor: '#181b22',
    zerolinecolor: '#23262e',
    linecolor: '#23262e',
    tickfont: { family: '"Cascadia Mono", "JetBrains Mono", monospace', size: 11, color: '#9ca3b0' },
    titlefont: { size: 12, color: '#d4d8e0' },
  },
  legend: {
    bgcolor: 'rgba(16, 18, 22, 0.88)',
    bordercolor: '#23262e',
    borderwidth: 1,
    font: { size: 11, color: '#d4d8e0' },
  },
  hovermode: 'closest',
};

export const PlotlyChart: React.FC<PlotlyChartProps> = React.memo(
  ({ data, layout, config, className = 'w-full h-80', onPointClick, onRangeSelect }) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const clickRef = useRef(onPointClick);
    const rangeRef = useRef(onRangeSelect);
    clickRef.current = onPointClick;
    rangeRef.current = onRangeSelect;

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;

      const mergedLayout = {
        ...BASE_DARK_LAYOUT,
        ...layout,
        xaxis: { ...(BASE_DARK_LAYOUT.xaxis as object), ...((layout?.xaxis as object) || {}) },
        yaxis: { ...(BASE_DARK_LAYOUT.yaxis as object), ...((layout?.yaxis as object) || {}) },
      };

      const mergedConfig = {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        ...config,
      };

      Plotly.react(el, data, mergedLayout, mergedConfig);

      const handlePlotlyClick = (ev: {
        points?: Array<{ x: number; y: number; curveNumber: number; pointIndex: number }>;
      }) => {
        if (clickRef.current && ev.points && ev.points.length > 0) {
          const pt = ev.points[0];
          clickRef.current({
            x: Number(pt.x),
            y: Number(pt.y),
            curveNumber: pt.curveNumber,
            pointIndex: pt.pointIndex,
          });
        }
      };

      const handleRelayout = (ev: Record<string, unknown>) => {
        if (
          rangeRef.current &&
          typeof ev['xaxis.range[0]'] === 'number' &&
          typeof ev['xaxis.range[1]'] === 'number'
        ) {
          rangeRef.current(Number(ev['xaxis.range[0]']), Number(ev['xaxis.range[1]']));
        }
      };

      const anyEl = el as unknown as {
        on: (event: string, cb: (...args: never[]) => void) => void;
        removeAllListeners?: (event: string) => void;
      };
      if (anyEl.removeAllListeners) {
        anyEl.removeAllListeners('plotly_click');
        anyEl.removeAllListeners('plotly_relayout');
      }
      anyEl.on('plotly_click', handlePlotlyClick as never);
      anyEl.on('plotly_relayout', handleRelayout as never);
    }, [data, layout, config]);

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const ro = new ResizeObserver(() => {
        if (containerRef.current) {
          Plotly.Plots.resize(containerRef.current);
        }
      });
      ro.observe(el);
      return () => {
        ro.disconnect();
        if (el) {
          Plotly.purge(el);
        }
      };
    }, []);

    return <div ref={containerRef} className={className} />;
  }
);
PlotlyChart.displayName = 'PlotlyChart';
