'use client'

import { Button } from '@/components/ui/Button'

export function RunControls({
  running,
  onPause,
  onResume,
  onStop
}: {
  running: boolean
  onPause: () => void
  onResume: () => void
  onStop: () => void
}) {
  return (
    <div className="flex items-center gap-2">
      {running ? <Button variant="secondary" onClick={onPause}>Pause</Button> : <Button variant="secondary" onClick={onResume}>Resume</Button>}
      <Button variant="danger" onClick={onStop}>Stop</Button>
    </div>
  )
}
