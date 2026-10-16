/** "viaje-japón, regalos" -> ["viaje-japón", "regalos"] (the API normalises them further). */
export function splitTags(text: string): string[] {
  return text
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
}
