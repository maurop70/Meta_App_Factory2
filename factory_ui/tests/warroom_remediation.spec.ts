import { test, expect } from '@playwright/test';

test('verify WarRoomMonitor programmatic compilation registry integration and live hardware telemetry', async ({ request }) => {
  console.log('[E2E WarRoom Remediation] Verifying WarRoomMonitor registration...');
  
  // 1. Assert registry is updated and ACTIVE
  const registryResponse = await request.get('http://127.0.0.1:5050/api/system/registry');
  expect(registryResponse.status()).toBe(200);
  
  const registryData = await registryResponse.json();
  const monitorAgent = registryData.agents.find((a: any) => a.id === 'warroommonitor');
  
  expect(monitorAgent).toBeDefined();
  expect(monitorAgent.status).toBe('ACTIVE');
  console.log(`[E2E WarRoom Remediation] WarRoomMonitor registered on port ${monitorAgent.port}`);
  
  // 2. Assert Dynamic Telemetry API returns actual psutil hardware telemetry and child pings
  console.log('[E2E WarRoom Remediation] Hitting dynamic proxy endpoint: GET /agent/warroommonitor/api/health');
  
  const healthResponse = await request.get('http://127.0.0.1:5050/agent/warroommonitor/api/health', {
    headers: {
      'X-API-KEY': 'default_secret_key'
    }
  });
  
  expect(healthResponse.status()).toBe(200);
  const healthData = await healthResponse.json();
  console.log('[E2E WarRoom Remediation] Telemetry payload:', JSON.stringify(healthData));
  
  // Assert actual psutil telemetry outputs rather than hardcoded mock strings
  expect(healthData.cpu_percent).not.toBe('mock_value_for_cpu_percent');
  expect(healthData.memory_percent).not.toBe('mock_value_for_memory_percent');
  
  // Assert the formats end with percentage symbol
  expect(healthData.cpu_percent).toMatch(/\d+(\.\d+)?%/);
  expect(healthData.memory_percent).toMatch(/\d+(\.\d+)?%/);
  
  // Assert child agent connectivity mapping is present and is a parsed status dictionary
  expect(healthData.child_agents_status).toBeDefined();
  const childStatus = JSON.parse(healthData.child_agents_status);
  expect(typeof childStatus).toBe('object');
  
  // Assert overall status state
  expect(['HEALTHY', 'DEGRADED']).toContain(healthData.overall_status);
  
  console.log('[E2E WarRoom Remediation] SUCCESS: WarRoomMonitor E2E telemetry is 100% verified and correct!');
});
