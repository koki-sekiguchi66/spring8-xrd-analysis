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
  plot_bgcolor: '#08090c',
  font: {
    family: '"Inter", "Segoe UI", "Yu Gothic UI", system-ui, sans-serif',
    color: '#98a0ae',
    size: 11,
  },
  margin: { l: 54, r: 16, t: 18, b: 40 },
  xaxis: {
    gridcolor: '#14171f',
    zerolinecolor: '#22262f',
    linecolor: '#22262f',
    tickfont: { family: '"JetBrains Mono", "Cascadia Mono", monospace', size: 10, color: '#858d9c' },
    titlefont: { size: 11, color: '#98a0ae' },
  },
  yaxis: {
    gridcolor: '#14171f',
    zerolinecolor: '#22262f',
    linecolor: '#22262f',
    tickfont: { family: '"JetBrains Mono", "Cascadia Mono", monospace', size: 10, color: '#858d9c' },
    titlefont: { size: 11, color: '#98a0ae' },
  },
  legend: {
    bgcolor: 'rgba(16, 18, 22, 0.90)',
    bordercolor: '#22262f',
    borderwidth: 1,
    font: { size: 10, color: '#cfd4de' },
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
