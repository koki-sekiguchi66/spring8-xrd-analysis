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
    'bg-gradient-to-b from-sky-400 to-sky-500 text-zinc-950 border border-sky-300/60 hover:from-sky-300 hover:to-sky-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35),0_4px_14px_-4px_rgba(56,189,248,0.45)] font-semibold',
  amber:
    'bg-gradient-to-b from-amber-400 to-amber-500 text-zinc-950 border border-amber-300/60 hover:from-amber-300 hover:to-amber-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35),0_4px_14px_-4px_rgba(245,158,11,0.4)] font-semibold',
  emerald:
    'bg-gradient-to-b from-emerald-400 to-emerald-500 text-zinc-950 border border-emerald-300/60 hover:from-emerald-300 hover:to-emerald-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35),0_4px_14px_-4px_rgba(52,211,153,0.4)] font-semibold',
  secondary:
    'bg-gradient-to-b from-[#202530] to-[#191d25] text-[#eef0f4] border border-[#303645] hover:from-[#262c39] hover:to-[#1f242e] hover:border-[#424a5e] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_2px_6px_-2px_rgba(0,0,0,0.5)] font-medium',
  ghost:
    'bg-transparent text-[#98a0ae] border border-transparent hover:bg-[#1a1e27] hover:text-[#eef0f4] font-medium',
  danger:
    'bg-rose-500/15 text-rose-200 border border-rose-500/40 hover:bg-rose-500/25 font-medium',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  xs: 'h-[30px] px-2.5 text-[12px] rounded-md gap-1.5',
  sm: 'h-[34px] px-3 text-[13px] rounded-md gap-1.5',
  md: 'h-[38px] px-4 text-[13px] rounded-md gap-2',
  lg: 'h-[44px] px-5 text-[14px] rounded-lg gap-2',
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
