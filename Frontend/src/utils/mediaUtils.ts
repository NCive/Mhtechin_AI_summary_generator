import { APP_CONFIG } from '../constants/appConstants';

/**
 * Resolves a media URL (audio/video) against the API base URL used by Axios.
 * - Absolute URLs (http://, https://, blob:, data:) are returned unchanged.
 * - Relative URLs (e.g. /api/v1/meetings/{id}/media) are resolved against the
 *   origin and base path of APP_CONFIG.API_BASE_URL so native <audio>/<video>
 *   elements request the backend server directly instead of the Vite dev server.
 */
export function resolveMediaUrl(url?: string | null): string {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!trimmed) return '';

  // Return unchanged if already absolute or a special browser scheme
  if (/^(?:[a-z]+:)?\/\//i.test(trimmed) || trimmed.startsWith('blob:') || trimmed.startsWith('data:')) {
    return trimmed;
  }

  const base = APP_CONFIG.API_BASE_URL || '';

  try {
    const defaultOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';
    const parsedBase = new URL(base, defaultOrigin);
    const origin = parsedBase.origin;
    const basePath = parsedBase.pathname.replace(/\/+$/, '');

    if (trimmed.startsWith('/')) {
      if (basePath && trimmed.startsWith(basePath)) {
        return `${origin}${trimmed}`;
      }
      return `${origin}${basePath}${trimmed}`;
    }

    return `${origin}${basePath}/${trimmed}`;
  } catch {
    if (trimmed.startsWith('/')) {
      return trimmed;
    }
    return `${base.replace(/\/+$/, '')}/${trimmed}`;
  }
}
