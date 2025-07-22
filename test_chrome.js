const puppeteer = require('puppeteer');

(async () => {
  try {
    console.log('[+] Testing Puppeteer with Chrome...');
    const browser = await puppeteer.launch({
      executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const page = await browser.newPage();
    await page.goto('https://www.google.com');
    console.log('[✓] Chrome launched successfully');
    console.log('[✓] Page title:', await page.title());
    
    await browser.close();
    console.log('[✓] Test completed successfully');
  } catch (error) {
    console.error('[✗] Test failed:', error.message);
    process.exit(1);
  }
})();
