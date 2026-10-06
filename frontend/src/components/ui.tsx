import { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "warn";

const variants: Record<Variant, string> = {
  primary:
    "bg-primary text-white hover:bg-blue-700 active:bg-blue-800 shadow-sm shadow-blue-600/20",
  secondary:
    "bg-white text-slate-700 ring-1 ring-slate-200 hover:ring-primary hover:text-primary active:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100 active:bg-slate-200",
  danger: "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm shadow-red-600/20",
  warn: "bg-amber-500 text-white hover:bg-amber-600 active:bg-amber-700",
};

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
}

export const Button = ({
  variant = "primary",
  size = "md",
  loading,
  className = "",
  children,
  disabled,
  ...rest
}: BtnProps) => (
  <button
    className={clsx(
      "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50",
      size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
      variants[variant],
      className,
    )}
    disabled={disabled || loading}
    {...rest}
  >
    {loading && (
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
    )}
    {children}
  </button>
);

export const Card = ({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) => (
  <section
    className={clsx(
      "rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-100 transition-shadow",
      className,
    )}
  >
    {children}
  </section>
);

export const Badge = ({
  children,
  tone = "slate",
  className = "",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "amber" | "red" | "blue" | "violet";
  className?: string;
}) => {
  const tones = {
    slate: "bg-slate-100 text-slate-600 ring-slate-200",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    amber: "bg-amber-50 text-amber-700 ring-amber-200",
    red: "bg-red-50 text-red-700 ring-red-200",
    blue: "bg-blue-50 text-blue-700 ring-blue-200",
    violet: "bg-violet-50 text-violet-700 ring-violet-200",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
};

export const Field = ({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) => (
  <label className="block">
    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
      {label}
    </span>
    {children}
    {hint && <span className="mt-1 block text-[11px] text-slate-400">{hint}</span>}
  </label>
);

const inputBase =
  "w-full rounded-xl border-0 bg-slate-50 px-3 py-2 text-sm text-slate-900 ring-1 ring-inset ring-slate-200 placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-primary transition";

export const Input = (props: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input {...props} className={clsx(inputBase, props.className)} />
);
export const Textarea = (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...props} className={clsx(inputBase, "min-h-[88px] resize-y", props.className)} />
);
export const Select = (props: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...props} className={clsx(inputBase, "appearance-none", props.className)} />
);

export const EmptyState = ({ icon = "🗂️", title, hint }: { icon?: string; title: string; hint?: string }) => (
  <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white/50 px-6 py-12 text-center">
    <div className="mb-3 text-3xl">{icon}</div>
    <p className="text-sm font-semibold text-slate-700">{title}</p>
    {hint && <p className="mt-1 max-w-sm text-xs text-slate-400">{hint}</p>}
  </div>
);
