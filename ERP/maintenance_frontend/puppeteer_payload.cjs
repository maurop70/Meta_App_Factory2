const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  // Intercept network requests to capture the exact response
  await page.setRequestInterception(true);
  page.on('request', request => {
    request.continue();
  });
  
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/mwo') && response.request().method() === 'POST') {
      try {
        console.log(`NETWORK RESPONSE CODE: ${response.status()}`);
        const text = await response.text();
        console.log(`NETWORK RESPONSE BODY: ${text}`);
      } catch (e) { }
    }
  });

  page.on('console', msg => {
    console.log('BROWSER CONSOLE:', msg.text());
  });

  try {
    await page.goto('http://localhost:5175/admin', { waitUntil: 'networkidle0', timeout: 10000 });
    
    console.log("Logging in...");
    await page.type('#mwo_operator_id', '9999');
    await page.type('#mwo_operator_pin', '1234');
    await page.click('button[type="submit"]');
    
    console.log("Waiting for Admin Console...");
    await page.waitForSelector('text/DM View', { timeout: 10000 }).catch(() => {});
    
    // Sometimes it's a button, let's find the DM View tab and click it
    const dmTab = await page.evaluateHandle(() => {
        const els = Array.from(document.querySelectorAll('*'));
        return els.find(el => el.textContent === 'DM View' && (el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'DIV'));
    });
    if (dmTab) {
        console.log("Actuating DM View tab...");
        await dmTab.click();
    } else {
        console.log("Could not find DM View tab");
    }

    console.log("Waiting for CreateMWOForm to mount...");
    await page.waitForSelector('select', { timeout: 5000 }).catch(() => {});
    
    // Fill the form
    console.log("Populating EQ-PLM-02, LOC-B payload...");
    await page.evaluate(() => {
        const selects = document.querySelectorAll('select');
        // Equipment select
        if(selects.length > 0) {
            Array.from(selects[0].options).forEach((opt, idx) => {
                if(opt.text.includes('Breakroom Sink')) selects[0].selectedIndex = idx;
            });
            selects[0].dispatchEvent(new Event('change', { bubbles: true }));
        }
        // Location select
        if(selects.length > 1) {
            Array.from(selects[1].options).forEach((opt, idx) => {
                if(opt.text.includes('LOC-B')) selects[1].selectedIndex = idx;
            });
            selects[1].dispatchEvent(new Event('change', { bubbles: true }));
        }
        // Urgency select
        if(selects.length > 2) {
            Array.from(selects[2].options).forEach((opt, idx) => {
                if(opt.text.includes('High')) selects[2].selectedIndex = idx;
            });
            selects[2].dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    const inputs = await page.$$('textarea, input[type="text"]');
    if (inputs.length > 0) {
        await inputs[inputs.length - 1].type('Backend UNASSIGNED test');
    }

    console.log("Executing Submit MWO...");
    const submitBtn = await page.evaluateHandle(() => {
        const els = Array.from(document.querySelectorAll('button'));
        return els.find(el => el.textContent.includes('Submit MWO'));
    });
    if (submitBtn) {
        await submitBtn.click();
        await new Promise(r => setTimeout(r, 2000)); // wait for network response
    } else {
        console.log("Submit MWO button not found!");
    }
    
  } catch (e) {
    console.log('RUNTIME ERROR:', e.message);
  }
  
  await browser.close();
})();
