import { useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { Button } from "./Button"

interface ShareModalProps {
  text: string
  onClose: () => void
}

// Shows the share text in a plain, selectable textbox instead of only trying
// navigator.clipboard.writeText directly: the Clipboard API requires a secure context, which a
// plain-HTTP self-hosted deployment (this project's default - see backend/src/config.py's
// cookie_secure) won't have. The textbox lets the player select-all and copy manually either way;
// the button is a one-click convenience that works whenever the Clipboard API is available.
// Visual shell copied from auth/RecentGamesModal.tsx's overlay/card pattern.
export function ShareModal({ text, onClose }: ShareModalProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      textareaRef.current?.select()
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-6"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-line-soft bg-surface p-6 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-ink">{t("daily.share.button")}</h2>
        <textarea
          ref={textareaRef}
          readOnly
          value={text}
          onFocus={(e) => e.target.select()}
          rows={text.split("\n").length + 1}
          className="mt-4 w-full resize-none rounded-xl border border-line-soft bg-app-bg p-3 font-mono text-sm text-ink outline-none focus:border-primary"
        />
        <div className="mt-4 flex gap-3">
          <Button variant="primary" className="flex-1 py-2.5" onClick={handleCopy}>
            {copied ? t("daily.share.copied") : t("daily.share.copyButton")}
          </Button>
          <Button variant="secondary" className="flex-1 py-2.5" onClick={onClose}>
            {t("common.back")}
          </Button>
        </div>
      </div>
    </div>
  )
}
