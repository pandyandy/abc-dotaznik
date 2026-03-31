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

function kbcReadDebug() {
  const v = process.env.DEBUG_KBC;
  return v !== '0' && String(v).toLowerCase() !== 'false';
}

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
 * Optional KeboolaUnload filter (smaller jobs / faster when tables are large).
 * @param {string} tableId
 * @param {{ whereColumn?: string, whereValues?: string[] }=} opts
 */
async function exportTable(tableId, opts = {}) {
  const args = ['export', tableId];
  if (opts.whereColumn && opts.whereValues?.length) {
    args.push('--where', opts.whereColumn, ...opts.whereValues.map(String));
  }
  const t0 = Date.now();
  if (kbcReadDebug()) {
    const filt =
      opts.whereColumn && opts.whereValues?.length
        ? ` WHERE ${opts.whereColumn} IN [${opts.whereValues.map(String).join(', ')}]`
        : '';
    console.log(`[Keboola read] → spawn export ${tableId}${filt}`);
  }
  const output = await runPython(args);
  const ms = Date.now() - t0;
  const rows = JSON.parse(output);
  if (kbcReadDebug()) {
    console.log(`[Keboola read] ← export ${tableId} done in ${ms}ms (${rows.length} rows)`);
  }
  return rows;
}

/**
 * Load rows into a Keboola Storage table.
 * rows: array of plain objects (keys = column names).
 * opts.incremental: when true, upserts via primary key instead of full-replacing the table.
 */
async function importTable(tableId, rows, opts = {}) {
  if (!rows || rows.length === 0) return;
  const args = ['import', tableId];
  if (opts.incremental) args.push('--incremental');
  await runPython(args, rows);
}

module.exports = { exportTable, importTable };
