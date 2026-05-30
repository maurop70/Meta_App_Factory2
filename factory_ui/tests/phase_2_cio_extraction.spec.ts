import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test.describe('Phase 2 - CIO Headless Intelligence Extraction & Validation Pipeline E2E Verification', () => {
  
  test('Should execute E2E extraction, poll status autonomously, and verify vector spatial persistence', async ({ request }) => {
    const targetUrl = 'http://127.0.0.1:5000/';
    
    console.log('[E2E Playwright] Starting CIO Extraction Pipeline test.');
    console.log(`[E2E Playwright] Target URL for extraction: ${targetUrl}`);

    // 1. Trigger the extraction endpoint on port 5000
    const extractResponse = await request.post('http://127.0.0.1:5000/api/cio/extract', {
      data: {
        url: targetUrl
      }
    });

    // Expecting 202 Accepted status code
    expect(extractResponse.status()).toBe(202);
    
    const extractBody = await extractResponse.json();
    console.log('[E2E Playwright] Initial response:', JSON.stringify(extractBody, null, 2));
    
    expect(extractBody.status).toBe('ACCEPTED');
    expect(extractBody.payload_id).toBeDefined();
    const payloadId = extractBody.payload_id;

    // 2. Synchronous E2E Polling Loop
    // Testing matrix is forbidden from executing raw database assertions immediately.
    let success = false;
    const maxAttempts = 30; // 30 attempts, 1 second apart = 30 seconds maximum
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      console.log(`[E2E Polling] Polling status endpoint for payload ${payloadId} (Attempt ${attempt}/${maxAttempts})...`);
      
      const statusResponse = await request.get(`http://127.0.0.1:5000/api/cio/status/${payloadId}`);
      expect(statusResponse.status()).toBe(200);
      
      const statusBody = await statusResponse.json();
      console.log(`[E2E Polling] Status response:`, JSON.stringify(statusBody, null, 2));

      if (statusBody.status === 'SUCCESS') {
        success = true;
        console.log(`[E2E Polling] Extraction registered SUCCESS!`);
        break;
      } else if (statusBody.status === 'FAILED') {
        throw new Error(`Extraction task failed in background: ${statusBody.error}`);
      }
      
      // Wait 1 second before the next poll
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    expect(success).toBe(true);

    // 3. ChromaDB Spatial Verification
    // Query the vector store to verify the document is registered and semantically retrievable
    console.log('[E2E Spatial Verification] Querying vector space for spatial verification...');
    const queryResponse = await request.post('http://127.0.0.1:5000/api/vector/query', {
      data: {
        query: 'Meta App Factory API version status',
        n_results: 5
      }
    });

    expect(queryResponse.status()).toBe(200);
    
    const queryBody = await queryResponse.json();
    console.log('[E2E Spatial Verification] Semantic query response:', JSON.stringify(queryBody, null, 2));
    
    expect(queryBody.status).toBe('SUCCESS');
    
    // Assert the document and payload ID exist within ChromaDB space
    const ids = queryBody.results.ids[0];
    expect(ids).toContain(payloadId);

    const documents = queryBody.results.documents[0];
    const docIndex = ids.indexOf(payloadId);
    expect(docIndex).toBeGreaterThanOrEqual(0);
    
    // Verify strict schema sanitization airgap
    const docContent = JSON.parse(documents[docIndex]);
    console.log('[E2E Spatial Verification] Sanitized document content:', JSON.stringify(docContent, null, 2));
    
    expect(docContent.core_concepts).toBeDefined();
    expect(Array.isArray(docContent.core_concepts)).toBe(true);
    expect(docContent.market_signals).toBeDefined();
    expect(Array.isArray(docContent.market_signals)).toBe(true);
    expect(docContent.threat_vectors).toBeDefined();
    expect(Array.isArray(docContent.threat_vectors)).toBe(true);

    console.log('[E2E Playwright] SUCCESS: Phase 2 CIO extraction & validation pipeline successfully verified.');
  });

  test('Should return a 409 Conflict if CIO_Agent is not active in the App Registry', async ({ request }) => {
    // Resolve registry.json path
    const registryPath = path.resolve(process.cwd(), '../registry.json');
    if (!fs.existsSync(registryPath)) {
      console.log(`[E2E 409 Test] registry.json not found at ${registryPath}. Skipping mutation check.`);
      return;
    }
    
    // 1. Read original registry
    const originalContent = fs.readFileSync(registryPath, 'utf8');
    const registryData = JSON.parse(originalContent);
    
    // Check if CIO_Agent exists
    if (!registryData.apps || !registryData.apps.CIO_Agent) {
      console.log('[E2E 409 Test] CIO_Agent not in registry.json. Skipping mutation check.');
      return;
    }
    
    const originalStatus = registryData.apps.CIO_Agent.status;
    
    try {
      // 2. Mutate CIO_Agent status to offline
      registryData.apps.CIO_Agent.status = 'offline';
      fs.writeFileSync(registryPath, JSON.stringify(registryData, null, 2), 'utf8');
      console.log('[E2E 409 Test] Registry mutated: CIO_Agent status set to offline.');
      
      // Allow a brief moment for the FS change to settle
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // 3. Make POST request and expect 409 Conflict on port 5000
      const extractResponse = await request.post('http://127.0.0.1:5000/api/cio/extract', {
        data: {
          url: 'http://127.0.0.1:5000/'
        }
      });
      
      expect(extractResponse.status()).toBe(409);
      const body = await extractResponse.json();
      expect(body.error).toBe('Agent Offline');
      expect(body.detail).toContain('CIO_Agent must be active');
      console.log('[E2E 409 Test] Successfully verified 409 Conflict rejection payload!');
      
    } finally {
      // 4. Restore original status
      registryData.apps.CIO_Agent.status = originalStatus;
      fs.writeFileSync(registryPath, JSON.stringify(registryData, null, 2), 'utf8');
      console.log('[E2E 409 Test] Registry restored to original state.');
    }
  });
});
