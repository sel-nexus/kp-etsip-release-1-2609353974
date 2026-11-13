import { afterEach, describe, expect, it, vi } from 'vitest';
import { getHealth, requestJson } from './client';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('requestJson', () => {
  it('returns parsed data for a successful response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    );
    await expect(getHealth()).resolves.toEqual({ status: 'ok' });
  });

  it('surfaces a safe API error message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'unavailable', message: 'Service unavailable' } }), { status: 503 }),
    );
    await expect(requestJson('/api/health')).rejects.toThrow('Service unavailable');
  });

  it('propagates network failures without hiding their cause', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Network unavailable'));
    await expect(requestJson('/api/health')).rejects.toThrow('Network unavailable');
  });
});
