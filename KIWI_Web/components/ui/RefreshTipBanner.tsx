'use client'

import { useEffect, useState } from 'react'

const REFRESH_TIP_KEY = 'kiwi_refresh_tip_dismissed'

export function RefreshTipBanner() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const isDismissed = localStorage.getItem(REFRESH_TIP_KEY) === '1'
    setShow(!isDismissed)
  }, [])

  if (!show) return null

  return (
    <div className="flex items-center gap-3 rounded-[var(--kiwi-radius)] border border-[#c5d9ff] bg-[#eef2ff] p-3 text-sm text-[#2d3f99]">
      <span className="shrink-0 text-lg">💡</span>
      <div className="flex-1">
        <span className="font-medium">Tip: </span>
        If a Scan or Run button looks stuck or inactive after changing batches, refresh the browser once. Your saved project should remain in place.
      </div>
      <button
        className="shrink-0 ml-2 text-lg hover:opacity-60 transition-opacity"
        onClick={() => {
          localStorage.setItem(REFRESH_TIP_KEY, '1')
          setShow(false)
        }}
        aria-label="Dismiss tip"
      >
        ✕
      </button>
    </div>
  )
}
