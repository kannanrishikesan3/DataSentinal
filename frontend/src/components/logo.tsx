/** The DataSentinel mark: a shield (Protect) with a magnifying glass
 * (Discover) — used as both the in-app logo (sidebar, login) and the
 * favicon (public/favicon.svg, same path data, kept in sync by hand since
 * the favicon is a static file the browser loads outside the app's CSS).
 *
 * The shield fill uses `currentColor` (set via the wrapping element's text
 * color); the magnifying-glass lines are drawn in `cutoutColor`, which
 * must match whatever surface the mark sits on for the glass to read as a
 * cutout rather than a mismatched halo — pass the actual background token
 * of that surface (defaults to the sidebar rail's own background, the
 * most common placement).
 */
export function Logo({ className, cutoutColor = 'var(--sidebar)' }: { className?: string; cutoutColor?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path d="M16 2 27 7v7.5C27 22.5 22 28.5 16 30.5 10 28.5 5 22.5 5 14.5V7Z" fill="currentColor" />
      <circle cx="14" cy="13" r="4.3" stroke={cutoutColor} strokeWidth="2.2" />
      <path d="M17.2 16.2 21 20" stroke={cutoutColor} strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}
