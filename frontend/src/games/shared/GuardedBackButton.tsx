import { useState } from "react"
import { useTranslation } from "react-i18next"

import { BackButton } from "./BackButton"
import { ConfirmExitModal } from "./ConfirmExitModal"

// Used mid-round instead of a plain BackButton: leaving here abandons the current round's
// unsubmitted guess (unlike the idle/error/finished screens' BackButton, which never has one), so
// it asks for confirmation first. The game itself is not abandoned - the idle screen's "Continuar"
// button on that mode's idle screen picks it back up exactly where this left it.
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
