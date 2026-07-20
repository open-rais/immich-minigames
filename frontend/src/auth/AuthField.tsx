import type { InputHTMLAttributes } from "react"

interface AuthFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  id: string
}

export function AuthField({ label, id, ...props }: AuthFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-semibold text-body">
        {label}
      </label>
      <input
        id={id}
        name={id}
        className="rounded-xl border border-line-soft bg-surface px-3.5 py-2.5 text-base text-ink outline-none transition-colors focus:border-primary"
        {...props}
      />
    </div>
  )
}
