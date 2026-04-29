const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('CONSOLE ERROR:', msg.text());
    }
  });
  
  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.toString());
  });
  
  try {
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('/mwo') && !url.includes('/technicians')) {
        try {
          const json = await response.json();
          const dataLength = Array.isArray(json.data) ? json.data.length : (Array.isArray(json) ? json.length : 0);
          console.log('TRACE EXACT URL:', url);
          console.log('TRACE PAYLOAD LENGTH:', dataLength);
        } catch (e) {}
      }
    });

    await page.goto('http://localhost:5175/admin', { waitUntil: 'networkidle0', timeout: 10000 });
    await page.type('#mwo_operator_id', '9999');
    await page.type('#mwo_operator_pin', '1234');
    await page.click('button[type="submit"]');
    
    // Wait for the HM View tab to appear and click it
    await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('HM View')), { timeout: 10000 });
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('HM View'));
      if (btn) btn.click();
    });
    
    await new Promise(r => setTimeout(r, 3000)); // Wait for fetch

  } catch (e) {
    console.log('RUNTIME ERROR:', e.message);
  }
  
  await browser.close();
})();
