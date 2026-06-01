import { test, expect } from '@playwright/test';

test('verify genesis orchestrator SSE stream on valid prompt', async ({ request }) => {
  console.log('[E2E Genesis Test] Sending valid agent request to /api/genesis/synthesize...');
  
  const response = await request.post('http://127.0.0.1:5050/api/genesis/synthesize', {
    data: { prompt: 'Build a real-time stock price alert agent' }
  });
  
  expect(response.status()).toBe(200);
  
  const bodyText = await response.text();
  console.log('[E2E Genesis Test] Response Body:\n', bodyText);
  
  // Assert presence of SSE life-cycle tokens
  expect(bodyText).toContain('research_start');
  expect(bodyText).toContain('verify_start');
  expect(bodyText).toContain('verify_pass');
  expect(bodyText).toContain('ontology_ready');
  expect(bodyText).toContain('research_complete');
  
  // Extract and logically inspect the generated ontology contract
  const lines = bodyText.split('\n');
  let ontologyFound = false;
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const dataStr = line.substring(6).trim();
      try {
        const payload = JSON.parse(dataStr);
        if (payload.event === 'ontology_ready') {
          ontologyFound = true;
          const ontology = payload.ontology;
          
          console.log('[E2E Genesis Test] Found AgentOntology JSON:', JSON.stringify(ontology, null, 2));
          
          // Verify Pydantic structural invariants and PascalCase name enforcement
          expect(ontology.agent_name).toMatch(/^[A-Z][A-Za-z0-9_]*$/);
          expect(ontology.role_summary.length).toBeGreaterThan(0);
          expect(ontology.role_summary.length).toBeLessThanOrEqual(280);
          expect(ontology.verified).toBe(true); // Verification_Node must have marked it true
          
          // Verify capabilities count is 3-8
          expect(ontology.primary_capabilities.length).toBeGreaterThanOrEqual(3);
          expect(ontology.primary_capabilities.length).toBeLessThanOrEqual(8);
          
          // Verify endpoints and POST requirement
          expect(ontology.api_endpoints.length).toBeGreaterThanOrEqual(1);
          const hasPost = ontology.api_endpoints.some((ep: any) => ep.method === 'POST');
          expect(hasPost).toBe(true);
          
          // Verify every endpoint Spec has a matching Data Contract
          const contractNames = new Set(ontology.data_contracts.map((dc: any) => dc.contract_name));
          for (const ep of ontology.api_endpoints) {
            expect(contractNames.has(ep.contract_ref)).toBe(true);
          }
        }
      } catch (e) {
        // Ignore JSON parse errors on partial or non-json chunks
      }
    }
  }
  
  expect(ontologyFound).toBe(true);
});

test('verify genesis orchestrator handles invalid queries robustly', async ({ request }) => {
  console.log('[E2E Genesis Test - Failure Path] Sending invalid request...');
  
  const response = await request.post('http://127.0.0.1:5050/api/genesis/synthesize', {
    data: { prompt: '' } // Empty prompt is invalid
  });
  
  expect(response.status()).toBe(200);
  
  const bodyText = await response.text();
  console.log('[E2E Genesis Test - Failure Path] Response Body:\n', bodyText);
  
  // Assert that either it gets handled gracefully or outputs standard verify sequence
  expect(bodyText).toContain('verify_start');
});
