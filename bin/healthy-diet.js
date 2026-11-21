#!/usr/bin/env node
'use strict';

const { spawn } = require('child_process');
const path = require('path');

const scriptPath = path.join(__dirname, '..', 'scripts', 'app.py');
const pythonCmd = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3');

const child = spawn(pythonCmd, [scriptPath, ...process.argv.slice(2)], {
  stdio: 'inherit'
});

child.on('error', (err) => {
  console.error(`[healthy-diet] Failed to spawn Python process: ${err.message}`);
  console.error('[healthy-diet] Please ensure Python 3.10+ is installed and available in PATH.');
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
