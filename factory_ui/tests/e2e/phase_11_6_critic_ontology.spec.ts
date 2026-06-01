import { test, expect } from '@playwright/test';

test.describe('Phase 11.6 - Critic Node Ontology Patch (Infrastructure Bypass Matrix)', () => {
  const CHALLENGE_API_URL = 'http://127.0.0.1:5000/api/warroom/challenge';

  test('Scenario 1: Internal Local Tailing Script triggers Infrastructure Bypass and is APPROVED', async ({ request }) => {
    const payload = {
      proposal: 'Design and deploy an Internal Local Tailing Script to aggregate daemon logs and orchestrate self-healing tasks.',
      critic_score: 5.0
    };

    const response = await request.post(CHALLENGE_API_URL, { data: payload });
    expect(response.status()).toBe(200);

    const body = await response.json();
    
    // Assert the Critic Node returned APPROVED status
    expect(body.status).toBe('APPROVED');
    
    // Assert the Infrastructure_Bypass flag is true
    expect(body.Infrastructure_Bypass).toBe(true);
    
    // Assert the validation mode is Auto-Approved
    expect(body.validation).toBe('Auto-Approved');

    // Assert the payload contains the Infrastructure Bypass Doctrine message
    expect(body.message).toContain('INFRASTRUCTURE BYPASS DOCTRINE');
    expect(body.message).toContain('permanently forbidden from evaluating it against external public SaaS constraints');
  });

  test('Scenario 2: Standard non-infrastructure proposal below threshold is PAUSED (Control group)', async ({ request }) => {
    const payload = {
      proposal: 'Build a public consumer SaaS marketplace for local organic produce, focusing on user acquisition and subscription models.',
      critic_score: 5.0
    };

    const response = await request.post(CHALLENGE_API_URL, { data: payload });
    expect(response.status()).toBe(200);

    const body = await response.json();

    // Assert standard SaaS proposal is PAUSED because it's below the 9.5 threshold and is not bypassed
    expect(body.status).toBe('PAUSED');
    expect(body.Infrastructure_Bypass).toBeUndefined();
    expect(body.gap).toBeGreaterThan(0);
    expect(body.weaknesses.length).toBe(3);
  });
});
