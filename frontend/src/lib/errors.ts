/** The message to show for a failed action: the API's (already in Spanish) or a fallback. */
export function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}
