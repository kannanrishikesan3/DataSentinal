import * as React from 'react'
import { Blurhash } from 'react-blurhash'

import { cn } from '@/lib/utils'

export interface BlurHashImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'width' | 'height'> {
  src: string
  blurHash?: string | null
  width?: number | string
  height?: number | string
  objectFit?: React.CSSProperties['objectFit']
}

export function BlurHashImage({
  src,
  blurHash,
  alt = '',
  className,
  width = '100%',
  height = '100%',
  objectFit = 'cover',
  onLoad,
  onError,
  loading = 'lazy',
  ...props
}: BlurHashImageProps) {
  const [loaded, setLoaded] = React.useState(false)
  const [failed, setFailed] = React.useState(false)

  React.useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [src])

  return (
    <div className={cn('relative overflow-hidden bg-slate-200 dark:bg-slate-800', className)} style={{ width, height }}>
      {!loaded && !failed && blurHash ? (
        <Blurhash
          hash={blurHash}
          width="100%"
          height="100%"
          resolutionX={32}
          resolutionY={32}
          className="absolute inset-0 h-full w-full"
          aria-hidden
        />
      ) : null}

      {!loaded && !failed && !blurHash ? (
        <div className="absolute inset-0 animate-pulse bg-slate-200 dark:bg-slate-800" aria-hidden />
      ) : null}

      {!failed ? (
        <img
          {...props}
          src={src}
          alt={alt}
          loading={loading}
          decoding="async"
          onLoad={(event) => {
            setLoaded(true)
            onLoad?.(event)
          }}
          onError={(event) => {
            setFailed(true)
            onError?.(event)
          }}
          className={cn(
            'absolute inset-0 h-full w-full transition-opacity duration-300',
            loaded ? 'opacity-100' : 'opacity-0',
          )}
          style={{ objectFit }}
        />
      ) : (
        <div
          role="img"
          aria-label={alt || 'Image failed to load'}
          className="absolute inset-0 flex items-center justify-center bg-slate-100 text-xs text-slate-500 dark:bg-slate-900 dark:text-slate-400"
        >
          Failed to load image
        </div>
      )}
    </div>
  )
}
