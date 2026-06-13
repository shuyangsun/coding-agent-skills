import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  Ref,
  TextareaHTMLAttributes,
} from "react";
import { Loader2 } from "lucide-react";

import { cn } from "#/lib/format";

// --- Button -----------------------------------------------------------------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost";
  size?: "sm" | "md";
};

const buttonVariants = {
  primary:
    "bg-accent text-accent-fg hover:brightness-110 disabled:opacity-50 disabled:hover:brightness-100",
  outline:
    "border border-edge bg-surface text-fg hover:border-edge-strong hover:bg-base disabled:opacity-50",
  ghost: "text-muted hover:bg-base hover:text-fg disabled:opacity-50",
} as const;

export function Button({
  variant = "outline",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/45 disabled:cursor-not-allowed",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        buttonVariants[variant],
        className,
      )}
      {...props}
    />
  );
}

// --- Segmented control ------------------------------------------------------
type SegmentedOption<T extends string> = {
  value: T;
  label: ReactNode;
  title?: string;
};

type SegmentedProps<T extends string> = {
  options: Array<SegmentedOption<T>>;
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  size?: "sm" | "md";
  className?: string;
};

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  size = "md",
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-edge bg-base p-0.5",
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.title}
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/45",
              size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm",
              active
                ? "bg-surface text-fg shadow-sm"
                : "text-muted hover:text-fg",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

// --- Toggle (switch) --------------------------------------------------------
type ToggleProps = {
  checked: boolean;
  onChange: (value: boolean) => void;
  label?: ReactNode;
  id?: string;
};

export function Toggle({ checked, onChange, label, id }: ToggleProps) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={typeof label === "string" ? label : undefined}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/45",
        checked ? "bg-accent" : "bg-edge-strong",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

// --- Badge ------------------------------------------------------------------
type BadgeTone = "neutral" | "accent" | "md" | "code";
const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-base text-muted border-edge",
  accent: "bg-accent-soft text-accent border-transparent",
  md: "bg-accent-soft text-accent border-transparent",
  code: "bg-code text-muted border-transparent",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[0.7rem] leading-none",
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// --- Spinner ----------------------------------------------------------------
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("animate-spin", className)} aria-hidden />;
}

// --- Field (label + hint wrapper) -------------------------------------------
export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={htmlFor}
        className="flex items-center justify-between text-xs font-medium text-muted"
      >
        <span>{label}</span>
        {hint ? <span className="font-normal text-faint">{hint}</span> : null}
      </label>
      {children}
    </div>
  );
}

// --- Inputs -----------------------------------------------------------------
const inputClass =
  "w-full rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-fg placeholder:text-faint transition focus-visible:outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/30";

export function TextInput({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(inputClass, className)} {...props} />;
}

export function TextArea({
  className,
  ref,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  ref?: Ref<HTMLTextAreaElement>;
}) {
  return (
    <textarea
      ref={ref}
      className={cn(inputClass, "resize-none", className)}
      {...props}
    />
  );
}

// --- Slider -----------------------------------------------------------------
export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  id,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  id?: string;
}) {
  return (
    <input
      id={id}
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => onChange(Number(event.target.value))}
      className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-edge-strong accent-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
    />
  );
}
