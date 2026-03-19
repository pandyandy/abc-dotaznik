import 'dotenv/config';
import express from 'express';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import FormData from 'form-data';
import { gunzipSync } from 'zlib';

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
app.use(express.json({ limit: '50mb' }));

const PORT = 8050;
const KEBOOLA_URL = (process.env.KBC_URL || process.env.KEBOOLA_URL || '').replace(/\/$/, '');
const TOKEN = process.env.KBC_TOKEN || process.env.STORAGE_API_TOKEN;

const TABLES = {
  trans_data:          'out.c-ABC.ABC_FORM_VALIDATION_DATA',
  fte_data:            'out.c-ABC.ABC_FORM_FTE',
  cc_user:             'out.c-ABC.ABC_FORM_CC_USER',
  saved_forms:         'out.c-ABC.ABC_FORM_ABC',
  saved_bs:            'out.c-ABC.ABC_FORM_BS',
  bl_order:            'out.c-ABC.ABC_FORM_BL_MAP',
  gpm_order:           'out.c-ABC.ABC_FORM_GPM_MAP',
  prod_mask_order:     'out.c-ABC.ABC_FORM_PROD_MAP',
  channel_mask_order:  'out.c-ABC.ABC_FORM_CHANNEL_MAP',
  version:             'out.c-ABC.ABC_VERSION',
  cc_desc:             'out.c-ABC.ABC_FORM_CC_DESC',
  trx_count:           'out.c-ABC.ABC_CALC_TRANSACTIONS',
};

// ==================== KEBOOLA API ====================

async function fetchWithRetry(url, opts, retries = 3, delayMs = 2000) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, opts);
    } catch (e) {
      if (i === retries - 1) throw e;
      console.warn(`  fetch failed (attempt ${i + 1}/${retries}): ${e.message} — retrying in ${delayMs}ms…`);
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}

async function kbcGet(path) {
  const res = await fetchWithRetry(`${KEBOOLA_URL}/v2/storage${path}`, {
    headers: { 'X-StorageApi-Token': TOKEN },
  });
  if (!res.ok) throw new Error(`Keboola GET ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function kbcPost(path, params) {
  const res = await fetchWithRetry(`${KEBOOLA_URL}/v2/storage${path}`, {
    method: 'POST',
    headers: {
      'X-StorageApi-Token': TOKEN,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams(params).toString(),
  });
  if (!res.ok) throw new Error(`Keboola POST ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function pollJob(jobId, label) {
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const job = await kbcGet(`/jobs/${jobId}`);
    console.log(`  [${label}] job ${jobId} → ${job.status} (${i * 2}s)`);
    if (job.status === 'success') return job;
    if (job.status === 'error') throw new Error(`Job ${jobId} failed: ${JSON.stringify(job.error)}`);
  }
  throw new Error(`Job ${jobId} timed out`);
}

async function exportTable(tableId) {
  const t0 = Date.now();
  const short = tableId.split('.').pop();
  console.log(`  [${short}] starting export…`);

  const [tableInfo, job] = await Promise.all([
    kbcGet(`/tables/${tableId}`),
    kbcPost(`/tables/${tableId}/export-async`, { format: 'rfc' }),
  ]);
  const columns = tableInfo.columns?.length ? tableInfo.columns : true;
  console.log(`  [${short}] job ${job.id} created, polling…`);

  const result = await pollJob(job.id, short);

  const fileId = result.results?.file?.id || result.file?.id;
  if (!fileId) throw new Error(`No file ID for ${tableId}: ${JSON.stringify(result.results)}`);

  // Get file info WITH federationToken to obtain the Azure SAS credentials
  console.log(`  [${short}] fetching file info (federationToken)…`);
  const fileInfo = await kbcGet(`/files/${fileId}?federationToken=1`);
  const creds = fileInfo.credentials || {};
  console.log(`  [${short}] provider=${fileInfo.provider}, credKeys=${Object.keys(creds).join(',') || 'none'}`);

  // For Azure, SAS token is embedded in the manifest URL query string
  let sas = creds.sas || '';
  if (!sas && creds.SASConnectionString) {
    const match = creds.SASConnectionString.match(/SharedAccessSignature=(.+)/);
    if (match) sas = match[1];
  }
  if (!sas && fileInfo.url) {
    const u = new URL(fileInfo.url);
    if (u.search) sas = u.search.slice(1); // strip leading '?'
  }
  console.log(`  [${short}] sas resolved: ${sas ? 'yes (' + sas.slice(0, 30) + '…)' : 'NO — will try without'}`);

  // The manifest URL returns JSON: {"entries":[{"url":"azure://..."}]}
  console.log(`  [${short}] downloading manifest…`);
  const manifestRes = await fetch(fileInfo.url);
  if (!manifestRes.ok) throw new Error(`Manifest download failed: ${manifestRes.status}`);
  const manifestText = await manifestRes.text();

  let csvText = '';

  let entries = null;
  try { entries = JSON.parse(manifestText).entries; } catch { /* not JSON — raw CSV */ }

  if (entries && entries.length > 0) {
    console.log(`  [${short}] downloading ${entries.length} blob(s)…`);
    const parts = await Promise.all(entries.map(async (entry, i) => {
      const httpsUrl = entry.url.replace(/^azure:\/\//, 'https://');
      const blobUrl = sas ? `${httpsUrl}?${sas}` : httpsUrl;
      const r = await fetch(blobUrl);
      if (!r.ok) throw new Error(`Blob ${i} failed: ${r.status} — URL: ${httpsUrl.slice(0, 100)}`);
      const buf = Buffer.from(await r.arrayBuffer());
      try { return gunzipSync(buf).toString('utf-8'); } catch { return buf.toString('utf-8'); }
    }));
    csvText = parts.join('');
  } else {
    csvText = manifestText;
  }

  const rows = parse(csvText, { columns, skip_empty_lines: true, relax_quotes: true });
  console.log(`  [${short}] done — ${rows.length} rows (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  return rows;
}

async function importTable(tableId, rows) {
  if (!rows || rows.length === 0) return;
  const short = tableId.split('.').pop();
  const csvContent = stringify(rows, { header: true });
  const csvBuf = Buffer.from(csvContent, 'utf-8');

  // 1. Create file resource and get Azure upload credentials
  const fileRes = await fetch(`${KEBOOLA_URL}/v2/storage/files/prepare`, {
    method: 'POST',
    headers: { 'X-StorageApi-Token': TOKEN, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ name: 'data.csv', sizeBytes: String(csvBuf.length), notify: '0', isPublic: '0', federationToken: '1' }).toString(),
  });
  if (!fileRes.ok) throw new Error(`File create failed: ${fileRes.status} ${await fileRes.text()}`);
  const fileInfo = await fileRes.json();
  const fileId = fileInfo.id;
  const absParams = fileInfo.absUploadParams;
  if (!absParams) throw new Error(`No absUploadParams in file prepare response for ${tableId}`);

  // 2. Build upload URL from absCredentials (sp=rwl — has write permission)
  const sasConn = absParams.absCredentials.SASConnectionString;
  const blobEndpointMatch = sasConn.match(/BlobEndpoint=([^;]+)/);
  const sasMatch = sasConn.match(/SharedAccessSignature=(.+)/);
  if (!blobEndpointMatch || !sasMatch) throw new Error(`Cannot parse SASConnectionString for ${tableId}`);
  const uploadUrl = `${blobEndpointMatch[1].replace(/\/$/, '')}/${absParams.container}/${absParams.blobName}?${sasMatch[1]}`;

  const uploadRes = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'x-ms-blob-type': 'BlockBlob', 'Content-Type': 'text/csv' },
    body: csvBuf,
  });
  if (!uploadRes.ok) throw new Error(`Azure upload failed: ${uploadRes.status}`);
  console.log(`  [${short}] file uploaded (id=${fileId})`);

  // 3. Trigger async incremental import
  const importJob = await kbcPost(`/tables/${tableId}/import-async`, {
    dataFileId: String(fileId),
    incremental: '1',
  });
  await pollJob(importJob.id, `${short}-import`);
  console.log(`  [${short}] import done`);
}

// ==================== CACHE ====================

const cache = {
  static: null, staticExpiry: 0,
  dynamic: null, dynamicExpiry: 0,
};

async function getStaticData() {
  if (cache.static && Date.now() < cache.staticExpiry) return cache.static;
  console.log('[abc] Loading static data…');
  const [transData, fteData, blOrder, gpmOrder, prodMaskOrder, channelMaskOrder, version, ccDesc, trxCount] =
    await Promise.all([
      exportTable(TABLES.trans_data),
      exportTable(TABLES.fte_data),
      exportTable(TABLES.bl_order),
      exportTable(TABLES.gpm_order),
      exportTable(TABLES.prod_mask_order),
      exportTable(TABLES.channel_mask_order),
      exportTable(TABLES.version),
      exportTable(TABLES.cc_desc),
      exportTable(TABLES.trx_count),
    ]);
  cache.static = { transData, fteData, blOrder, gpmOrder, prodMaskOrder, channelMaskOrder, version, ccDesc, trxCount };
  cache.staticExpiry = Date.now() + 10 * 60 * 1000;
  return cache.static;
}

async function getDynamicData(force = false) {
  if (!force && cache.dynamic && Date.now() < cache.dynamicExpiry) return cache.dynamic;
  const [ccUser, savedForms, savedBs] = await Promise.all([
    exportTable(TABLES.cc_user),
    exportTable(TABLES.saved_forms),
    exportTable(TABLES.saved_bs).catch(() => []),
  ]);
  cache.dynamic = { ccUser, savedForms, savedBs };
  cache.dynamicExpiry = Date.now() + 30 * 1000;
  return cache.dynamic;
}

// ==================== API ROUTES ====================

function checkEnv(res) {
  if (!TOKEN || !KEBOOLA_URL) {
    res.status(500).json({ error: 'Missing KEBOOLA_URL or STORAGE_API_TOKEN env vars' });
    return false;
  }
  return true;
}

app.get('/api/data', async (req, res) => {
  if (!checkEnv(res)) return;
  try { res.json(await getStaticData()); }
  catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

app.get('/api/dynamic-data', async (req, res) => {
  if (!checkEnv(res)) return;
  try { res.json(await getDynamicData(true)); }
  catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

app.post('/api/save-form', async (req, res) => {
  if (!checkEnv(res)) return;
  try {
    const { rows, cc, version } = req.body;
    const current = cache.dynamic?.savedForms || await exportTable(TABLES.saved_forms).catch(() => []);
    const filtered = current.filter(r =>
      !(String(r.CC || '').trim() === String(cc).trim() &&
        String(r.VERSION || '').trim() === String(version).trim())
    );
    const updated = [...filtered, ...rows];
    await importTable(TABLES.saved_forms, updated);
    if (cache.dynamic) cache.dynamic.savedForms = updated;
    res.json({ ok: true });
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

app.post('/api/save-bs', async (req, res) => {
  if (!checkEnv(res)) return;
  try {
    const { rows, cc, version } = req.body;
    const current = cache.dynamic?.savedBs || await exportTable(TABLES.saved_bs).catch(() => []);
    const filtered = current.filter(r =>
      !(String(r.COST_CENTER || '').trim() === String(cc).trim() &&
        String(r.VERSION || '').trim() === String(version).trim())
    );
    const updated = [...filtered, ...rows];
    await importTable(TABLES.saved_bs, updated);
    if (cache.dynamic) cache.dynamic.savedBs = updated;
    res.json({ ok: true });
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

// Serve frontend — app.all handles Keboola's POST to /
app.all('/', (req, res) => res.sendFile(join(__dirname, 'index.html')));
app.use(express.static(__dirname, { index: false }));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[abc] Listening on port ${PORT}`);
  getStaticData().catch(e => console.error('[abc] Preload static failed:', e));
  getDynamicData().catch(e => console.error('[abc] Preload dynamic failed:', e));
});
