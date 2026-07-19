import { describe, expect, it, vi } from 'vitest'
import { api } from './client'

describe('api client', () => {
  it('returns decoded JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ready' }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(api('/health')).resolves.toEqual({ status: 'ready' })
  })
})

