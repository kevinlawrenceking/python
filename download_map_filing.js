const puppeteer = require('puppeteer');
const fs = require('fs-extra');
const path = require('path');
const { spawn } = require('child_process');

const FILE_NAME = process.env.FILE_NAME;
const KEY = process.env.KEY;
const END = process.env.END;
const COOKIE = process.env.COOKIE;
const FK_CASE = process.env.FK_CASE || 'Unfiled';
const COURT_CASE_NUMBER = process.env.COURT_CASE_NUMBER || 'Unfiled';
const IS_UNFILED = process.env.IS_UNFILED === "true";

if (!FILE_NAME || !COOKIE) {
  console.error('[×] Missing one or more required environment variables.');
  process.exit(1);
}

const VIEWER_URL = `https://ww2.lacourt.org/documentviewer/v1/?name=${FILE_NAME}&key=${KEY || ''}&end=${END || ''}`;
const SAVE_DIR = path.resolve(__dirname, 'temp_pages');
fs.ensureDirSync(SAVE_DIR);

(async () => {
  console.log(`[+] Launching Chromium...`);
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: null,
    protocolTimeout: 60000, // Increase protocol timeout to 60 seconds
    args: [
      '--start-maximized',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage'
    ]
  });

  const page = await browser.newPage();
  
  // Configure page for better performance with large documents
  await page.setDefaultNavigationTimeout(120000); // 2 minute navigation timeout
  await page.setDefaultTimeout(60000); // 1 minute timeout for other operations
  
  // Optimize for memory usage (especially helpful for large documents)
  await page.setRequestInterception(true);
  page.on('request', (request) => {
    // Block non-essential resources to improve performance
    const resourceType = request.resourceType();
    if (['media', 'font', 'stylesheet'].includes(resourceType)) {
      request.abort();
    } else {
      request.continue();
    }
  });
  
  // Set up error handler
  page.on('error', err => {
    console.error(`[!] Page crashed: ${err}`);
  });
  
  page.on('pageerror', err => {
    console.error(`[!] Error in page: ${err}`);
  });

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
  let maxIterations = 200; // Increased from 100
  let iteration = 0;

  while (stableCount < 15 && iteration < maxIterations) { // Increased from 5 to 15
    iteration++;
    
    // Dynamic wait time based on document size and iteration count
    // For larger documents or later iterations, wait longer
    const baseWaitTime = 3000;
    const additionalWait = Math.min(iteration * 500, 7000); // Increase wait time as we progress, up to 7s additional
    const waitTime = baseWaitTime + additionalWait;
    
    console.log(`[→] Waiting ${waitTime/1000}s for page to stabilize...`);
    await new Promise(resolve => setTimeout(resolve, waitTime));
    
    const newUrls = await page.evaluate(() =>
      Array.from(document.images).map(img => img.src).filter(u => u.includes('page='))
    );

    const fresh = newUrls.filter(u => !seen.has(u));
    fresh.forEach(u => seen.add(u));

    console.log(`[→] Iteration ${iteration}: Found ${newUrls.length} total images, ${fresh.length} new images`);

    if (seen.size === lastSeen) {
      stableCount++;
      console.log(`[→] No new images found. Stable count: ${stableCount}/15`);
    } else {
      stableCount = 0;
      lastSeen = seen.size;
      console.log(`[→] Total unique images: ${seen.size}`);
    }

    // Try multiple ways to navigate to next page - with improved error handling
    let clicked;
    try {
      // Split the complex evaluate calls into smaller, more focused ones
      // to help prevent timeouts
      
      // Method 1: Look for "Next Page" button
      clicked = await page.evaluate(() => {
        try {
          let nextBtn = Array.from(document.querySelectorAll('span.ui-button-text'))
            .find(el => el && el.innerText && el.innerText.trim().toLowerCase() === 'next page');
          
          if (nextBtn && !nextBtn.closest('button').disabled) {
            nextBtn.click();
            return 'next_button';
          }
          return null;
        } catch (e) {
          console.error("Error in Method 1:", e);
          return null;
        }
      });
      
      if (!clicked) {
        // Method 2: Look for arrow buttons or page navigation
        clicked = await page.evaluate(() => {
          try {
            const arrows = document.querySelectorAll('[title*="Next"], [aria-label*="Next"], .ui-icon-seek-next, .ui-icon-triangle-1-e');
            for (let arrow of arrows) {
              if (arrow && arrow.offsetParent !== null && !arrow.closest('button')?.disabled) {
                arrow.click();
                return 'arrow_button';
              }
            }
            return null;
          } catch (e) {
            console.error("Error in Method 2:", e);
            return null;
          }
        });
      }
      
      if (!clicked) {
        // Method 3: Look for common navigation elements by selector
        clicked = await page.evaluate(() => {
          try {
            // Common selectors for pagination
            const selectors = [
              '.next', 
              '.next-page', 
              '[aria-label="Next"]', 
              '.pagination-next',
              '.pagination .next',
              '.page-item:not(.disabled) .page-link[aria-label="Next"]'
            ];
            
            for (const selector of selectors) {
              const element = document.querySelector(selector);
              if (element && element.offsetParent !== null && !element.disabled) {
                element.click();
                return 'selector_based_next';
              }
            }
            return null;
          } catch (e) {
            console.error("Error in Method 3:", e);
            return null;
          }
        });
      }
      
      if (!clicked) {
        // Method 4: Try keyboard navigation as last resort
        clicked = await page.evaluate(() => {
          try {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
            return 'keyboard_right';
          } catch (e) {
            console.error("Error in Method 4:", e);
            return null;
          }
        });
      }
    } catch (err) {
      console.error(`[!] Error during navigation evaluation: ${err.message}`);
      clicked = 'navigation_error';
    }

    console.log(`[→] Navigation attempt: ${clicked || 'none_found'}`);
    
    if (!clicked || clicked === 'navigation_error') {
      console.log('[→] Navigation unsuccessful, trying alternative methods');
      
      // Check if we've reached the end by looking for disabled next buttons or "last page" indicators
      const isLastPage = await page.evaluate(() => {
        try {
          // Check for disabled next buttons
          const disabledNextBtn = document.querySelector('.ui-button-text-only[disabled], .page-link.next.disabled, .ui-state-disabled .ui-icon-seek-next');
          if (disabledNextBtn) return true;
          
          // Check for text indicating last page
          const pageText = document.body.innerText.toLowerCase();
          const lastPageIndicators = ['last page', 'end of document', 'no more pages'];
          if (lastPageIndicators.some(text => pageText.includes(text))) return true;
          
          return false;
        } catch (e) {
          return false;
        }
      });
      
      if (isLastPage) {
        console.log('[→] Detected last page indicators, likely reached the end of document');
        stableCount = 15; // Force exit from the loop
      } else {
        // Try scrolling down to load more content
        await page.evaluate(() => {
          window.scrollTo(0, document.body.scrollHeight);
        });
        await new Promise(resolve => setTimeout(resolve, 3000)); // Increased wait time
        
        // Try clicking anywhere on the right side of the page
        try {
          await page.evaluate(() => {
            const rect = document.body.getBoundingClientRect();
            const x = rect.width * 0.8; // Right side
            const y = rect.height / 2; // Middle height
            const element = document.elementFromPoint(x, y);
            if (element) {
              element.click();
              return true;
            }
            return false;
          });
        } catch (err) {
          console.error(`[!] Error during right-side click: ${err.message}`);
        }
      }
    }
  }

  if (iteration >= maxIterations) {
    console.log('[!] Reached maximum iterations, stopping page navigation');
  }

  console.log(`[→] Total pages detected: ${seen.size}`);
  console.log(`[!] Final wait before closing...`);
  await new Promise(resolve => setTimeout(resolve, 5000));
  await browser.close();

  console.log(`[+] Generating PDF for case ID: ${FK_CASE}`);
  const py = spawn('python', ['combine_images_to_pdf.py'], {
    env: {
      ...process.env,
      COURT_CASE_NUMBER: COURT_CASE_NUMBER,
      FK_CASE: FK_CASE
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
