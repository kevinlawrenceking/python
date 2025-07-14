const { spawn } = require('child_process');

const py = spawn('python', ['combine_images_to_pdf.py'], {
  env: { COURT_CASE_NUMBER: 'E745908455' },
  cwd: __dirname
});

py.stdout.on('data', data => console.log('[PY STDOUT]', data.toString()));
py.stderr.on('data', data => console.error('[PY STDERR]', data.toString()));
py.on('close', code => console.log(`[PY EXIT CODE]: ${code}`));
