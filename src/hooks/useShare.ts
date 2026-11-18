import { useState, useCallback } from 'react';

interface ShareOptions {
  title: string;
  text?: string;
  url?: string;
}

export function useShare() {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const share = useCallback(async (options: ShareOptions): Promise<boolean> => {
    setError(null);
    const shareUrl = options.url || window.location.href;

    if (navigator.share) {
      try {
        await navigator.share({
          title: options.title,
          text: options.text || options.title,
          url: shareUrl,
        });
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
        return true;
      } catch (err: unknown) {
        if ((err as Error)?.name !== 'AbortError') {
          // If native share failed for reasons other than user canceling, fallback to clipboard
          try {
            await navigator.clipboard.writeText(shareUrl);
            setCopied(true);
            setTimeout(() => setCopied(false), 3000);
            return true;
          } catch {
            setError('Failed to copy link to clipboard.');
            return false;
          }
        }
        return false;
      }
    } else {
      // Fallback to clipboard
      try {
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
        return true;
      } catch {
        setError('Clipboard access is restricted.');
        return false;
      }
    }
  }, []);

  return { share, copied, error };
}
