import React from 'react';
import { cn } from '../../lib/utils';

export type ButtonVariant = 'primary' | 'amber' | 'emerald' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-sky-500 text-zinc-950 border border-sky-400/40 hover:bg-sky-400 active:bg-sky-500 font-semibold',
  amber:
    'bg-amber-500 text-zinc-950 border border-amber-400/40 hover:bg-amber-400 active:bg-amber-500 font-semibold',
  emerald:
    'bg-emerald-500 text-zinc-950 border border-emerald-400/40 hover:bg-emerald-400 active:bg-emerald-500 font-semibold',
  secondary:
    'bg-[#1c1f26] text-[#eceef2] border border-[#2d323e] hover:bg-[#232730] hover:border-[#3b4252] font-medium',
  ghost:
    'bg-transparent text-[#9ca3b0] border border-transparent hover:bg-[#1c1f26] hover:text-[#eceef2] font-medium',
  danger:
    'bg-rose-500/15 text-rose-200 border border-rose-500/40 hover:bg-rose-500/25 font-medium',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  xs: 'h-7 px-2.5 text-xs rounded-md gap-1.5',
  sm: 'h-8 px-3 text-[13px] rounded-md gap-1.5',
  md: 'h-9 px-3.5 text-[13px] rounded-lg gap-2',
  lg: 'h-10 px-4 text-sm rounded-lg gap-2',
};

/** Precision flat action button without decorative gradients or glow. */
export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  block = false,
  type = 'button',
  className,
  children,
  ...rest
}) => {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 disabled:cursor-not-allowed disabled:opacity-45 select-none',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        block && 'w-full',
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
};
