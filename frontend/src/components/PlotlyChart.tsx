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
  plot_bgcolor: '#09090b',
  font: {
    family: '"Cascadia Mono", "JetBrains Mono", Consolas, monospace',
    color: '#e4e4e7',
    size: 13,
  },
  margin: { l: 64, r: 24, t: 38, b: 48 },
  xaxis: {
    gridcolor: '#1f1f23',
    zerolinecolor: '#27272a',
    linecolor: '#27272a',
    tickfont: { size: 12, color: '#d4d4d8' },
    titlefont: { size: 14, color: '#f4f4f5' },
  },
  yaxis: {
    gridcolor: '#1f1f23',
    zerolinecolor: '#27272a',
    linecolor: '#27272a',
    tickfont: { size: 12, color: '#d4d4d8' },
    titlefont: { size: 14, color: '#f4f4f5' },
  },
  legend: {
    bgcolor: 'rgba(18, 18, 22, 0.90)',
    bordercolor: '#27272a',
    borderwidth: 1,
    font: { size: 12, color: '#f4f4f5' },
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

      const handlePlotlyClick = (ev: { points?: Array<{ x: number; y: number; curveNumber: number; pointIndex: number }> }) => {
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

      // Attach listeners cleanly
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
