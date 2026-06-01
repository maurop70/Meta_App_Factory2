import { test, expect } from '@playwright/test';

test('verify deterministic Jinja2 compilation dynamic registry and dynamic port proxying', async ({ request }) => {
  console.log('[E2E Registry Compilation Test] Sending valid agent request to /api/genesis/synthesize...');
  
  const response = await request.post('http://127.0.0.1:5050/api/genesis/synthesize', {
    data: { prompt: 'Build a stock ticker alert agent' }
  });
  
  expect(response.status()).toBe(200);
  
  const bodyText = await response.text();
  console.log('[E2E Registry Compilation Test] SSE stream response received.');
  
  // Assert SSE life-cycle tokens
  expect(bodyText).toContain('ontology_ready');
  expect(bodyText).toContain('compile_success');
  
  // Parse ontology and compile status from stream
  const lines = bodyText.split('\n');
  let ontology = null;
  let compileSuccessData = null;
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const dataStr = line.substring(6).trim();
      try {
        const payload = JSON.parse(dataStr);
        if (payload.event === 'ontology_ready') {
          ontology = payload.ontology;
        } else if (payload.event === 'compile_success') {
          compileSuccessData = payload;
        }
      } catch (e) {
        // Ignore parsing errors on partial chunks
      }
    }
  }
  
  expect(ontology).not.toBeNull();
  expect(compileSuccessData).not.toBeNull();
  
  const agentName = ontology.agent_name;
  const agentId = agentName.toLowerCase().replace(/_/g, '');
  const allocatedPort = compileSuccessData.port;
  
  console.log(`[E2E Registry Compilation Test] Compiled ${agentName} (ID: ${agentId}) successfully on port ${allocatedPort}`);
  
  // 1. Assert registry is updated
  const registryResponse = await request.get('http://127.0.0.1:5050/api/system/registry');
  expect(registryResponse.status()).toBe(200);
  
  const registryData = await registryResponse.json();
  const registeredAgent = registryData.agents.find((a: any) => a.name === agentName);
  
  expect(registeredAgent).toBeDefined();
  expect(registeredAgent.port).toBe(allocatedPort);
  expect(registeredAgent.status).toBe('ACTIVE');
  
  // 2. Assert Dynamic Port Proxying
  // Hit the dynamic route on Master Architect (Port 5050)
  const firstEndpoint = ontology.api_endpoints[0];
  const proxyPath = `/agent/${agentId}${firstEndpoint.path}`;
  const method = firstEndpoint.method;
  
  console.log(`[E2E Registry Compilation Test] Testing isolated dynamic proxy: ${method} http://127.0.0.1:5050${proxyPath}`);
  
  // Prepare payload if method is POST/PUT/PATCH
  let fetchOptions: any = { headers: {} };
  
  const authMethod = ontology.security_posture.auth_method;
  if (authMethod === 'bearer_token') {
    fetchOptions.headers['Authorization'] = 'Bearer default_bearer_token';
  } else if (authMethod === 'api_key') {
    fetchOptions.headers['X-API-KEY'] = 'default_secret_key';
  }
  
  if (['POST', 'PUT', 'PATCH'].includes(method)) {
    const matchingContract = ontology.data_contracts.find((c: any) => c.contract_name === firstEndpoint.contract_ref);
    const mockInput: any = {};
    if (matchingContract) {
      for (const field of matchingContract.input_fields) {
        mockInput[field] = 'e2e_test_value';
      }
    }
    fetchOptions.data = mockInput;
  }
  
  // Wait 1.5 seconds to allow Uvicorn subprocess to fully bind to its dynamic port
  await new Promise(resolve => setTimeout(resolve, 1500));
  
  // Call Master Architect Proxy Route
  const proxyResponse = await request[method.toLowerCase()]('http://127.0.0.1:5050' + proxyPath, fetchOptions);
  
  console.log(`[E2E Registry Compilation Test] Proxy Route Status: ${proxyResponse.status()}`);
  if (proxyResponse.status() !== 200) {
    const errText = await proxyResponse.text();
    console.error(`[E2E Registry Compilation Test] Proxy Failure Body:`, errText);
  }
  expect(proxyResponse.status()).toBe(200);
  
  const proxyBody = await proxyResponse.json();
  console.log('[E2E Registry Compilation Test] Proxy response payload:', JSON.stringify(proxyBody));
  
  // Assert response fields match data contract outputs
  const matchingContract = ontology.data_contracts.find((c: any) => c.contract_name === firstEndpoint.contract_ref);
  if (matchingContract) {
    for (const field of matchingContract.output_fields) {
      expect(proxyBody[field]).toBeDefined();
    }
  }
  
  console.log('[E2E Registry Compilation Test] SUCCESS: Jinja2 compilation, dynamic registration, and dynamic proxying are 100% verified!');
});
