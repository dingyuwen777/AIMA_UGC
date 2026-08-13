import { healthLive } from '../generated/api/client'

export function fetchHealth() {
  return healthLive()
}
