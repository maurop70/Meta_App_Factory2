const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  // Set up authentication state for headless traversal
  await page.evaluateOnNewDocument(() => {
    document.cookie = "refresh_token=mocked; path=/;";
    window.localStorage.setItem('role', 'ADMIN');
  });

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
  
  try {
    await page.goto('http://localhost:5175/admin', { waitUntil: 'networkidle0', timeout: 10000 });
  } catch (e) {
    console.log('GOTO ERROR:', e.message);
  }
  
  await browser.close();
})();
