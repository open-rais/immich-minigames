import { useState } from "react"

import { personThumbnailUrl } from "../api/games"

// Same img+onError fallback convention as menu/UserMenu.tsx's SkinAvatar / games/shared/
// PersonAvatar.tsx, just sized as a page hero avatar instead of a small circle. Shared by
// ProfilePage.tsx (read-only) and EditProfilePage.tsx (live preview while picking a skin) -
// render with `key={personId}` at the call site so switching skins resets `failed` instead of
// keeping a stale placeholder around.
export function ProfileAvatar({ personId }: { personId: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <ProfileAvatarPlaceholder />
  return (
    <img
      src={personThumbnailUrl(personId)}
      alt=""
      onError={() => setFailed(true)}
      className="h-24 w-24 rounded-full object-cover shadow-card"
    />
  )
}

export function ProfileAvatarPlaceholder() {
  return <div className="h-24 w-24 rounded-full border border-dashed border-line-strong" />
}
