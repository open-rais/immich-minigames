import { useState } from "react"
import { useTranslation } from "react-i18next"

import { BackButton } from "./BackButton"
import { ConfirmExitModal } from "./ConfirmExitModal"

// Used mid-round instead of a plain BackButton: leaving here discards the game in progress, so it
// asks for confirmation first (unlike the idle/error/finished screens' BackButton, which never has
// a run to lose).
export function GuardedBackButton({ onExit }: { onExit: () => void }) {
  const { t } = useTranslation()
  const [confirming, setConfirming] = useState(false)

  return (
    <>
      <BackButton label={t("common.back")} onClick={() => setConfirming(true)} />
      {confirming && <ConfirmExitModal onConfirm={onExit} onCancel={() => setConfirming(false)} />}
    </>
  )
}
