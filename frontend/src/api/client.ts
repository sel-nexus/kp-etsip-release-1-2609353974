import type { ApiErrorEnvelope } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Call a JSON API route and surface safe server or transport errors. */
export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('The API request could not be completed.');
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as ApiErrorEnvelope;
      message = body.error?.message ?? message;
    } catch (error) {
      if (!(error instanceof SyntaxError)) {
        throw error;
      }
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

/** Read API liveness through the same-origin API path. */
export function getHealth(): Promise<{ status: 'ok' }> {
  return requestJson<{ status: 'ok' }>('/api/health');
}
