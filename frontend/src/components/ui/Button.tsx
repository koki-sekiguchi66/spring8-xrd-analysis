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
    'bg-sky-500 text-zinc-950 border border-sky-400/50 hover:bg-sky-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)] font-semibold',
  amber:
    'bg-amber-500 text-zinc-950 border border-amber-400/50 hover:bg-amber-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)] font-semibold',
  emerald:
    'bg-emerald-500 text-zinc-950 border border-emerald-400/50 hover:bg-emerald-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)] font-semibold',
  secondary:
    'bg-[#1b1f27] text-[#eef0f4] border border-[#2c313d] hover:bg-[#222732] hover:border-[#394050] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.045)] font-medium',
  ghost:
    'bg-transparent text-[#98a0ae] border border-transparent hover:bg-[#1a1d25] hover:text-[#eef0f4] font-medium',
  danger:
    'bg-rose-500/15 text-rose-200 border border-rose-500/35 hover:bg-rose-500/25 font-medium',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  xs: 'h-[26px] px-2 text-[11px] rounded gap-1',
  sm: 'h-[30px] px-2.5 text-[12px] rounded-md gap-1.5',
  md: 'h-[34px] px-3 text-[12px] rounded-md gap-1.5',
  lg: 'h-[38px] px-4 text-[13px] rounded-md gap-2',
};

/** Tactile hardware-inspired flat action button. */
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
        'inline-flex items-center justify-center whitespace-nowrap transition-colors duration-100 active:translate-y-[0.5px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500/70 disabled:cursor-not-allowed disabled:opacity-40 select-none',
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
