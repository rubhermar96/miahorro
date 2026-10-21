import { type RefObject, useEffect, useState } from 'react'

/** The rendered width of an element, kept up to date, so charts draw at real pixel sizes and
 * their text never shrinks with the screen. */
export function useWidth(ref: RefObject<HTMLElement | null>, fallback = 320): number {
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const element = ref.current
    if (!element) {
      return
    }
    const measure = () => {
      const measured = element.getBoundingClientRect().width
      if (measured > 0) {
        setWidth(Math.round(measured))
      }
    }
    measure()
    if (typeof ResizeObserver === 'undefined') {
      return
    }
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return width
}
