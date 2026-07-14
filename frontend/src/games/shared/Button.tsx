import type { ButtonHTMLAttributes } from "react"

type Variant = "primary" | "secondary" | "danger"

const variantClass: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary: "border border-line-soft bg-surface text-body hover:bg-hover-tint",
  danger: "border border-danger bg-surface text-danger hover:border-danger-hover hover:bg-danger-hover hover:text-white",
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

/** Shared pill button - callers supply padding/flex layout via `className` (deliberately not
 * baked in here, since the guess buttons and the standalone screen buttons need different ones). */
export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`rounded-full text-[15px] font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${variantClass[variant]} ${className}`}
      {...props}
    />
  )
}
