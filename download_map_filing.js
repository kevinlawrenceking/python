const puppeteer = require('puppeteer');
const fs = require('fs-extra');
const path = require('path');
const { spawn } = require('child_process');

const FILE_NAME = process.env.FILE_NAME;
const KEY = process.env.KEY;
const END = process.env.END;
const COOKIE = process.env.COOKIE;
const FK_CASE = process.env.FK_CASE || 'Unfiled';  // This should be the case ID
const COURT_CASE_NUMBER = process.env.COURT_CASE_NUMBER || 'Unfiled';  // This should be court case number
const IS_UNFILED = process.env.IS_UNFILED === "true";

if (!FILE_NAME || !COOKIE || (!IS_UNFILED && (!KEY || !END))) {
  console.error('[×] Missing one or more required environment variables.');
  process.exit(1);
}

const VIEWER_URL = `https://ww2.lacourt.org/documentviewer/v1/?name=${FILE_NAME}&key=${KEY}&end=${END}`;
const SAVE_DIR = path.resolve(__dirname, 'temp_pages');
fs.ensureDirSync(SAVE_DIR);

(async () => {
  console.log(`[+] Launching Chromium...`);
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: null,
    args: [
      '--start-maximized',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage'
    ]
  });

  const page = await browser.newPage();

  await page.setCookie({
    name: '.AspNetCore.Cookies',
    value: COOKIE,
    domain: 'ww2.lacourt.org',
    path: '/',
    httpOnly: true,
    secure: true
  });

  const seen = new Set();

  page.on('response', async (res) => {
    const url = res.url();
    const ct = res.headers()['content-type'] || '';
    if (ct.startsWith('image') && url.includes('page=')) {
      try {
        const buffer = await res.buffer();
        const match = url.match(/page=(\d+)/);
        const pageNum = match ? match[1].padStart(3, '0') : 'unknown';
        const filename = `${FILE_NAME}_page_${pageNum}.png`;
        const filePath = path.join(SAVE_DIR, filename);
        if (!seen.has(url)) {
          await fs.writeFile(filePath, buffer);
          seen.add(url);
          console.log(`[✓] Saved: ${filename}`);
        }
      } catch (err) {
        console.error(`[×] Failed to save image from ${url}`, err);
      }
    }
  });

  try {
    console.log(`[+] Navigating to viewer: ${VIEWER_URL}`);
    await page.goto(VIEWER_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  } catch (err) {
    console.error(`[×] Viewer page load failed:`, err.message);
    await browser.close();
    process.exit(1);
  }

  console.log(`[→] Clicking 'Next Page' until all pages load...`);
  let lastSeen = 0;
  let stableCount = 0;

  while (stableCount < 3) {
    const newUrls = await page.evaluate(() =>
      Array.from(document.images).map(img => img.src).filter(u => u.includes('page='))
    );

    const fresh = newUrls.filter(u => !seen.has(u));
    fresh.forEach(u => seen.add(u));

    if (seen.size === lastSeen) {
      stableCount++;
    } else {
      stableCount = 0;
      lastSeen = seen.size;
    }

    const clicked = await page.evaluate(() => {
      const nextBtn = Array.from(document.querySelectorAll('span.ui-button-text'))
        .find(el => el.innerText.trim().toLowerCase() === 'next page');
      if (nextBtn) {
        nextBtn.click();
        return true;
      }
      return false;
    });

    if (!clicked) {
      console.log('[!] "Next Page" button not found — exiting.');
      break;
    }

    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  console.log(`[→] Total pages detected: ${seen.size}`);
  console.log(`[!] Final wait before closing...`);
  await new Promise(resolve => setTimeout(resolve, 5000));
  await browser.close();

  console.log(`[+] Generating PDF for case ID: ${FK_CASE}`);
  const py = spawn('python', ['combine_images_to_pdf.py'], {
    env: {
      ...process.env,
      COURT_CASE_NUMBER: COURT_CASE_NUMBER,  // Pass court case number correctly
      FK_CASE: FK_CASE  // Pass case ID correctly
    },
    cwd: __dirname
  });

  let pythonOutput = '';
  let pythonError = '';

  py.stdout.on('data', data => {
    const output = data.toString();
    pythonOutput += output;
    process.stdout.write(output);
  });

  py.stderr.on('data', data => {
    const error = data.toString();
    pythonError += error;
    process.stderr.write(error);
  });

  py.on('close', code => {
    if (code === 0) {
      console.log(`[✓] combine_images_to_pdf.py completed successfully`);
      
      // Check if PDF was actually created
      const expectedPdfPath = path.join(__dirname, 'docs', 'cases', FK_CASE);
      if (fs.existsSync(expectedPdfPath)) {
        const pdfFiles = fs.readdirSync(expectedPdfPath).filter(f => f.endsWith('.pdf'));
        if (pdfFiles.length > 0) {
          console.log(`[✓] PDF generated and saved: ${path.join(expectedPdfPath, pdfFiles[0])}`);
        } else {
          console.error(`[×] No PDF files found in ${expectedPdfPath}`);
        }
      } else {
        console.error(`[×] Expected PDF directory not found: ${expectedPdfPath}`);
      }
    } else {
      console.error(`[×] combine_images_to_pdf.py exited with code ${code}`);
      console.error(`[×] Python stderr: ${pythonError}`);
    }
    
    // Clean up temp files
    try {
      fs.removeSync(SAVE_DIR);
      console.log(`[✓] Cleaned up temp directory: ${SAVE_DIR}`);
    } catch (err) {
      console.error(`[×] Failed to clean up temp directory: ${err.message}`);
    }
  });

  py.on('error', (err) => {
    console.error(`[×] Failed to start Python script: ${err.message}`);
    process.exit(1);
  });
})();
