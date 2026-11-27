export function formatServiceRequestId(id: number): string {
  return `SR-${String(id).padStart(5, '0')}`
}
