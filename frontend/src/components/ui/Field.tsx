import React from 'react';
import { cn } from '../../lib/utils';

export interface FieldLabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  hint?: string;
}

/** Compact property label. */
export const FieldLabel: React.FC<FieldLabelProps> = ({
  hint,
  className,
  children,
  ...rest
}) => {
  return (
    <label
      className={cn('flex items-center justify-between gap-2 text-[11px] font-medium text-[#858d9c] mb-1', className)}
      {...rest}
    >
      <span className="truncate">{children}</span>
      {hint && <span className="font-mono text-[10px] text-[#5d6473] shrink-0">{hint}</span>}
    </label>
  );
};

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
}

/** Recessed hardware-well text input. */
export const TextInput: React.FC<TextInputProps> = ({
  mono = false,
  className,
  ...rest
}) => {
  return (
    <input
      className={cn(
        'w-full h-[30px] rounded-md border border-[#262a34] bg-[#08090c] px-2.5 text-[12px] text-[#eef0f4] placeholder-[#5d6473] transition-colors focus:border-sky-500/70 focus:outline-none focus:ring-1 focus:ring-sky-500/25',
        mono && 'font-mono',
        className
      )}
      {...rest}
    />
  );
};

export interface UnitNumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  unit?: string;
}

/** Numeric input with flush unit cap and tabular-nums alignment. */
export const UnitNumberInput: React.FC<UnitNumberInputProps> = ({
  unit,
  className,
  ...rest
}) => {
  return (
    <div
      className={cn(
        'flex items-center h-[30px] rounded-md border border-[#262a34] bg-[#08090c] focus-within:border-sky-500/70 focus-within:ring-1 focus-within:ring-sky-500/25 transition-colors overflow-hidden',
        className
      )}
    >
      <input
        type="number"
        className="w-full h-full bg-transparent px-2 text-[12px] font-mono tabular-nums text-[#eef0f4] placeholder-[#5d6473] focus:outline-none min-w-0"
        {...rest}
      />
      {unit && (
        <span className="px-2 text-[10px] font-mono text-[#5d6473] border-l border-[#1d2028] bg-[#101216] h-full flex items-center shrink-0 select-none">
          {unit}
        </span>
      )}
    </div>
  );
};

export interface SelectInputProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  mono?: boolean;
}

/** Dark select control. */
export const SelectInput: React.FC<SelectInputProps> = ({
  mono = false,
  className,
  children,
  ...rest
}) => {
  return (
    <select
      className={cn(
        'w-full h-[30px] rounded-md border border-[#262a34] bg-[#08090c] px-2 text-[12px] text-[#eef0f4] transition-colors focus:border-sky-500/70 focus:outline-none focus:ring-1 focus:ring-sky-500/25',
        mono && 'font-mono',
        className
      )}
      {...rest}
    >
      {children}
    </select>
  );
};

export interface CheckboxRowProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: React.ReactNode;
  className?: string;
}

/** Compact toggle row. */
export const CheckboxRow: React.FC<CheckboxRowProps> = ({
  checked,
  onChange,
  label,
  className,
}) => {
  return (
    <label className={cn('inline-flex items-center gap-2 text-[12px] text-[#cfd4de] cursor-pointer select-none', className)}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-3.5 rounded border-[#303644] bg-[#08090c] accent-sky-500"
      />
      <span>{label}</span>
    </label>
  );
};
