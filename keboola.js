'use strict';

/**
 * keboola.js — thin Node.js wrapper around keboola_io.py.
 *
 * All Keboola Storage API calls are handled by the official Python client
 * (kbcstorage). This module spawns the Python script as a child process
 * and communicates via stdin/stdout JSON.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Use the uv-managed venv when available (Keboola production),
// otherwise fall back to system python3 (local development).
const VENV_PYTHON = path.join(__dirname, '.venv', 'bin', 'python3');
const PYTHON = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
const SCRIPT = path.join(__dirname, 'keboola_io.py');

function runPython(args, inputData = null) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [SCRIPT, ...args], {
      env: process.env,
    });

    const stdoutChunks = [];
    const stderrChunks = [];

    proc.stdout.on('data', (chunk) => stdoutChunks.push(chunk));
    proc.stderr.on('data', (chunk) => stderrChunks.push(chunk));

    proc.on('close', (code) => {
      const stderr = Buffer.concat(stderrChunks).toString().trim();
      if (code !== 0) {
        reject(new Error(`keboola_io.py [${args.join(' ')}] failed (exit ${code}): ${stderr}`));
        return;
      }
      if (stderr) {
        // Surface Python warnings to Node logs without failing
        console.warn('[keboola_io]', stderr);
      }
      resolve(Buffer.concat(stdoutChunks).toString());
    });

    proc.on('error', (err) => reject(new Error(`Failed to spawn Python: ${err.message}`)));

    if (inputData !== null) {
      proc.stdin.write(JSON.stringify(inputData));
    }
    proc.stdin.end();
  });
}

/**
 * Export a Keboola Storage table and return its rows as an array of objects.
 * Column names are normalised to UPPERCASE.
 */
async function exportTable(tableId) {
  const output = await runPython(['export', tableId]);
  return JSON.parse(output);
}

/**
 * Full-replace a Keboola Storage table with the given rows.
 * rows: array of plain objects (keys = column names).
 */
async function importTable(tableId, rows) {
  if (!rows || rows.length === 0) return;
  await runPython(['import', tableId], rows);
}

module.exports = { exportTable, importTable };
