import { healthLive } from '../generated/api'

export function fetchHealth() {
  return healthLive()
}
