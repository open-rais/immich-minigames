import { useTranslation } from "react-i18next"

import { Button } from "./Button"

interface ConfirmExitModalProps {
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmExitModal({ onConfirm, onCancel }: ConfirmExitModalProps) {
  const { t } = useTranslation()
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-6"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-line-soft bg-surface p-6 text-center shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-ink">{t("common.exitConfirm.title")}</h2>
        <p className="mt-2 text-sm text-muted">{t("common.exitConfirm.message")}</p>
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="danger" className="px-5 py-2.5" onClick={onConfirm}>
            {t("common.exitConfirm.confirm")}
          </Button>
          <Button variant="secondary" className="px-5 py-2.5" onClick={onCancel}>
            {t("common.exitConfirm.cancel")}
          </Button>
        </div>
      </div>
    </div>
  )
}
