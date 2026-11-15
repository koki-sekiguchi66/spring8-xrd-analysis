import React from 'react';
import { cn } from '../../lib/utils';

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: 'surface' | 'inset' | 'chrome';
}

const TONE_CLASSES = {
  surface:
    'bg-[#15181e] border border-[#22262f] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.035)]',
  inset: 'bg-[#08090c] border border-[#1f232c]',
  chrome: 'bg-[#101216] border border-[#22262f]',
};

/** Primary machined container with subtle specular top edge and hairline borders. */
export const Panel: React.FC<PanelProps> = ({
  tone = 'surface',
  className,
  children,
  ...rest
}) => {
  return (
    <div className={cn('rounded-md', TONE_CLASSES[tone], className)} {...rest}>
      {children}
    </div>
  );
};

export interface PanelHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}

/** Compact header strip for Panels. */
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
        'px-3.5 py-2 border-b border-[#22262f] flex flex-wrap items-center justify-between gap-2',
        className
      )}
      {...rest}
    >
      <div className="flex items-baseline gap-2 min-w-0">
        <div className="text-[12px] font-semibold tracking-tight text-[#eef0f4] truncate">
          {title}
        </div>
        {subtitle && (
          <div className="text-[11px] font-mono tabular-nums text-[#5d6473] truncate">
            {subtitle}
          </div>
        )}
      </div>
      {actions && <div className="flex items-center gap-1.5 shrink-0">{actions}</div>}
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
    <div className={cn('p-3.5', className)} {...rest}>
      {children}
    </div>
  );
};
