import React from 'react';
import { cn } from '../../lib/utils';

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: 'surface' | 'inset' | 'chrome';
}

const TONE_CLASSES = {
  surface: 'bg-[#16181d] border border-[#23262e]',
  inset: 'bg-[#0a0b0e] border border-[#23262e]',
  chrome: 'bg-[#121418] border border-[#23262e]',
};

/** Primary structural container with hairline borders and calibrated surface depth. */
export const Panel: React.FC<PanelProps> = ({
  tone = 'surface',
  className,
  children,
  ...rest
}) => {
  return (
    <div className={cn('rounded-lg', TONE_CLASSES[tone], className)} {...rest}>
      {children}
    </div>
  );
};

export interface PanelHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}

/** Compact single-line or two-line header bar for Panels. */
export const PanelHeader: React.FC<PanelHeaderProps> = ({
  title,
  subtitle,
  actions,
  className,
  ...rest
}) => {
  return (
    <div
      className={cn(
        'px-4 py-2.5 border-b border-[#23262e] flex flex-wrap items-center justify-between gap-2.5',
        className
      )}
      {...rest}
    >
      <div className="min-w-0">
        <div className="text-[13px] font-semibold text-[#eceef2] truncate">{title}</div>
        {subtitle && <div className="text-xs text-[#9ca3b0] truncate mt-0.5">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
};

/** Main content region inside a Panel. */
export const PanelBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...rest
}) => {
  return (
    <div className={cn('p-4', className)} {...rest}>
      {children}
    </div>
  );
};
