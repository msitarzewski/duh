export function GridOverlay() {
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden opacity-[0.03]">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern
            id="circuit-grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 40 0 L 0 0 0 40"
              fill="none"
              stroke="var(--color-primary)"
              strokeWidth="0.5"
            />
          </pattern>
          <pattern
            id="circuit-grid-lg"
            width="200"
            height="200"
            patternUnits="userSpaceOnUse"
          >
            <rect width="200" height="200" fill="url(#circuit-grid)" />
            <path
              d="M 200 0 L 0 0 0 200"
              fill="none"
              stroke="var(--color-primary)"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#circuit-grid-lg)" />
      </svg>
    </div>
  )
}
