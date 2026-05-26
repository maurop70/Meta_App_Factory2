import { test, expect } from '@playwright/test';

test.describe('Inventory Endpoint Boot Resilience', () => {
  const INVENTORY_API_URL = 'http://127.0.0.1:5050/api/inventory';

  test('Scenario 1: GET request to inventory returns 200 OK on uninitialized/empty DB', async ({ request }) => {
    const response = await request.get(`${INVENTORY_API_URL}?limit=10&offset=0`);
    
    // Assert 200 OK even if the table doesn't exist yet
    expect(response.status()).toBe(200);
  });

  test('Scenario 2: Response payload strictly adheres to unified pagination envelope', async ({ request }) => {
    const response = await request.get(`${INVENTORY_API_URL}?limit=10&offset=0`);
    expect(response.status()).toBe(200);

    const body = await response.json();

    // Assert the response payload strictly contains the items, total, limit, and offset keys
    expect(body).toHaveProperty('items');
    expect(Array.isArray(body.items)).toBeTruthy();
    
    expect(body).toHaveProperty('total');
    expect(typeof body.total).toBe('number');

    expect(body).toHaveProperty('limit');
    expect(typeof body.limit).toBe('number');

    expect(body).toHaveProperty('offset');
    expect(typeof body.offset).toBe('number');

    // No extra keys should exist, ensuring strict envelope adherence
    const keys = Object.keys(body);
    expect(keys).toContain('items');
    expect(keys).toContain('total');
    expect(keys).toContain('limit');
    expect(keys).toContain('offset');
    expect(keys.length).toBe(4);
  });
});
