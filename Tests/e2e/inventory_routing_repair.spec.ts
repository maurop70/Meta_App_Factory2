import { test, expect } from '@playwright/test';

test.describe('Inventory Proxy Routing Resiliency', () => {
  const UI_PROXY_URL = 'http://127.0.0.1:5173/api/inventory';

  test('Assert 404 Not Found is mathematically eradicated and yields 200 OK', async ({ request }) => {
    const response = await request.get(`${UI_PROXY_URL}?limit=5&offset=0`);
    
    // Assert Vite proxy successfully forwards and resolves the route with 200 OK
    expect(response.status()).toBe(200);
  });

  test('Assert the strictly formatted pagination envelope matches doctrine exactly', async ({ request }) => {
    const response = await request.get(`${UI_PROXY_URL}?limit=5&offset=0`);
    expect(response.status()).toBe(200);

    const body = await response.json();

    // Verify properties and structural types of the uniform pagination envelope
    expect(body).toHaveProperty('items');
    expect(Array.isArray(body.items)).toBeTruthy();
    
    expect(body).toHaveProperty('total');
    expect(typeof body.total).toBe('number');

    expect(body).toHaveProperty('limit');
    expect(typeof body.limit).toBe('number');
    expect(body.limit).toBe(5);

    expect(body).toHaveProperty('offset');
    expect(typeof body.offset).toBe('number');
    expect(body.offset).toBe(0);

    // Enforce NGINX Reverse-Proxy Decoupling rules — no extra envelope padding allowed
    const envelopeKeys = Object.keys(body);
    expect(envelopeKeys).toContain('items');
    expect(envelopeKeys).toContain('total');
    expect(envelopeKeys).toContain('limit');
    expect(envelopeKeys).toContain('offset');
    expect(envelopeKeys.length).toBe(4);
  });
});
