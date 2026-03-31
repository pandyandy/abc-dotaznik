'use strict';

require('dotenv').config();

const express = require('express');
const path = require('path');
const { exportTable, importTable } = require('./keboola');

const app = express();
const PORT = process.env.PORT || 3000;

const TABLES = {
  trans_data: 'out.c-ABC.ABC_FORM_VALIDATION_DATA',
  fte_data: 'out.c-ABC.ABC_FORM_FTE',
  cc_user: 'out.c-ABC.ABC_FORM_CC_USER',
  saved_forms: 'out.c-ABC.ABC_FORM_ABC',
  saved_bs: 'out.c-ABC.ABC_FORM_BS',
  bl_order: 'out.c-ABC.ABC_FORM_BL_MAP',
  gpm_order: 'out.c-ABC.ABC_FORM_GPM_MAP',
  prod_mask_order: 'out.c-ABC.ABC_FORM_PROD_MAP',
  channel_mask_order: 'out.c-ABC.ABC_FORM_CHANNEL_MAP',
  version: 'out.c-ABC.ABC_VERSION',
  cc_desc: 'out.c-ABC.ABC_FORM_CC_DESC',
  trx_count: 'out.c-ABC.ABC_CALC_TRANSACTIONS',
};

/** One combined cache for the full dataset (fewer round-trips to Storage on first load). */
let dataCache = null;
let dataCacheTime = 0;
const CACHE_TTL = Number(process.env.DATA_CACHE_TTL_MS) || 5 * 60 * 1000;

/** Storage read tracing: logs to stdout. Set DEBUG_KBC=0 to turn off. */
function kbcReadDebug() {
  const v = process.env.DEBUG_KBC;
  return v !== '0' && String(v).toLowerCase() !== 'false';
}

function kbcReadLog(message, detail) {
  if (!kbcReadDebug()) return;
  if (detail !== undefined) console.log('[Keboola read]', message, detail);
  else console.log('[Keboola read]', message);
}

function num(val) {
  const n = parseFloat(String(val).replace(',', '.'));
  return isNaN(n) ? 0 : n;
}

function nowSk() {
  return new Date().toLocaleString('sk-SK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).replace(/\//g, '.');
}

/** All Storage exports in one wave (wall time ≈ slowest table, not sum of waves). */
async function exportAllTablesRaw() {
  kbcReadLog('12-table parallel export starting…');
  const t0 = Date.now();
  const [
    rawVersion,
    rawTransData,
    rawFteData,
    rawBlOrder,
    rawGpmOrder,
    rawProdMask,
    rawChannelMask,
    rawCcDesc,
    rawTrxCount,
    rawCcUser,
    rawSavedForms,
    rawSavedBs,
  ] = await Promise.all([
    exportTable(TABLES.version),
    exportTable(TABLES.trans_data),
    exportTable(TABLES.fte_data),
    exportTable(TABLES.bl_order),
    exportTable(TABLES.gpm_order),
    exportTable(TABLES.prod_mask_order),
    exportTable(TABLES.channel_mask_order),
    exportTable(TABLES.cc_desc),
    exportTable(TABLES.trx_count),
    exportTable(TABLES.cc_user),
    exportTable(TABLES.saved_forms),
    exportTable(TABLES.saved_bs),
  ]);
  const ms = Date.now() - t0;
  kbcReadLog(`12-table parallel export finished in ${ms}ms`, {
    rowCounts: {
      version: rawVersion.length,
      trans_data: rawTransData.length,
      fte_data: rawFteData.length,
      bl_map: rawBlOrder.length,
      gpm_map: rawGpmOrder.length,
      prod_map: rawProdMask.length,
      channel_map: rawChannelMask.length,
      cc_desc: rawCcDesc.length,
      trx_count: rawTrxCount.length,
      cc_user: rawCcUser.length,
      saved_forms: rawSavedForms.length,
      saved_bs: rawSavedBs.length,
    },
  });

  return {
    rawVersion,
    rawTransData,
    rawFteData,
    rawBlOrder,
    rawGpmOrder,
    rawProdMask,
    rawChannelMask,
    rawCcDesc,
    rawTrxCount,
    rawCcUser,
    rawSavedForms,
    rawSavedBs,
  };
}

function processRawToPayload(r) {
  const versionsSorted = [...r.rawVersion].sort(
    (a, b) => parseInt(b.VERSION_ID) - parseInt(a.VERSION_ID)
  );
  const actVersionRow = versionsSorted[0];
  const prevVersionRow = versionsSorted[1] || null;
  const actVersion = actVersionRow?.VERSION || '';
  const prevVersion = prevVersionRow?.VERSION || null;

  const transData = r.rawTransData.filter(
    (row) =>
      String(row.VERSION || row.version || '').trim() === String(actVersion).trim() ||
      String(row.version || '').toLowerCase().trim() === 'act'
  );

  const trxCount = r.rawTrxCount.filter(
    (row) => String(row.version || row.VERSION || '').toLowerCase().trim() === 'act'
  );

  const validVersions = [String(actVersion)];
  if (prevVersion) validVersions.push(String(prevVersion));

  const savedForms = r.rawSavedForms.filter((row) =>
    validVersions.includes(String(row.VERSION || '').trim())
  );
  const savedBs = r.rawSavedBs.filter((row) =>
    validVersions.includes(String(row.VERSION || '').trim())
  );

  return {
    transData,
    fteData: r.rawFteData,
    blOrder: r.rawBlOrder,
    gpmOrder: r.rawGpmOrder,
    prodMaskOrder: r.rawProdMask,
    channelMaskOrder: r.rawChannelMask,
    ccDesc: r.rawCcDesc,
    trxCount,
    actVersion,
    prevVersion,
    versions: r.rawVersion,
    ccUser: r.rawCcUser,
    savedForms,
    savedBs,
  };
}

async function loadFreshPayloadFromKeboola() {
  const raw = await exportAllTablesRaw();
  const payload = processRawToPayload(raw);
  kbcReadLog('payload built', {
    actVersion: payload.actVersion,
    prevVersion: payload.prevVersion || null,
    transDataRows: payload.transData.length,
    savedFormsRows: payload.savedForms.length,
    savedBsRows: payload.savedBs.length,
  });
  return payload;
}

async function getCachedPayload() {
  if (dataCache && Date.now() - dataCacheTime < CACHE_TTL) {
    kbcReadLog(`cache hit (age ${Date.now() - dataCacheTime}ms, ttl ${CACHE_TTL}ms)`);
    return dataCache;
  }
  kbcReadLog('cache miss → fetching from Storage…');
  dataCache = await loadFreshPayloadFromKeboola();
  dataCacheTime = Date.now();
  return dataCache;
}

/** Dynamic slice only; VERSION-filtered exports (smaller jobs when tables are large). */
async function loadDynamicData(actVersion, prevVersion) {
  const versions = [String(actVersion).trim()];
  const pv = prevVersion != null && prevVersion !== '' ? String(prevVersion).trim() : null;
  if (pv) versions.push(pv);

  kbcReadLog('dynamic-data: 3 parallel exports starting…', {
    VERSION: versions,
    tables: [TABLES.cc_user, TABLES.saved_forms, TABLES.saved_bs],
  });

  const where = { whereColumn: 'VERSION', whereValues: versions };
  const t0 = Date.now();
  const [rawCcUser, rawSavedForms, rawSavedBs] = await Promise.all([
    exportTable(TABLES.cc_user),
    exportTable(TABLES.saved_forms, where),
    exportTable(TABLES.saved_bs, where),
  ]);
  const ms = Date.now() - t0;

  const validVersions = versions;
  const savedForms = rawSavedForms.filter((row) =>
    validVersions.includes(String(row.VERSION || '').trim())
  );
  const savedBs = rawSavedBs.filter((row) =>
    validVersions.includes(String(row.VERSION || '').trim())
  );

  kbcReadLog(`dynamic-data: finished in ${ms}ms`, {
    ccUser: rawCcUser.length,
    savedForms: savedForms.length,
    savedBs: savedBs.length,
  });

  return { ccUser: rawCcUser, savedForms, savedBs };
}

function staticSlice(payload) {
  const { ccUser, savedForms, savedBs, ...rest } = payload;
  return rest;
}

function dynamicSlice(payload) {
  return {
    ccUser: payload.ccUser,
    savedForms: payload.savedForms,
    savedBs: payload.savedBs,
  };
}

function versionKeysForCache(actVersion, prevVersion) {
  const v = String(actVersion).trim();
  const keys = [v];
  if (prevVersion != null && prevVersion !== '')
    keys.push(String(prevVersion).trim());
  return keys;
}

/** Keep static slice; refresh only saved_* after import (one Storage export). */
async function mergeSavedFormsIntoCache(actVersion) {
  const keys = dataCache
    ? versionKeysForCache(actVersion, dataCache.prevVersion)
    : [String(actVersion).trim()];
  const raw = await exportTable(TABLES.saved_forms, {
    whereColumn: 'VERSION',
    whereValues: keys,
  });
  const savedForms = raw.filter((row) =>
    keys.includes(String(row.VERSION || '').trim())
  );
  if (dataCache) dataCache.savedForms = savedForms;
  return savedForms;
}

async function mergeSavedBsIntoCache(actVersion) {
  const keys = dataCache
    ? versionKeysForCache(actVersion, dataCache.prevVersion)
    : [String(actVersion).trim()];
  const raw = await exportTable(TABLES.saved_bs, {
    whereColumn: 'VERSION',
    whereValues: keys,
  });
  const savedBs = raw.filter((row) =>
    keys.includes(String(row.VERSION || '').trim())
  );
  if (dataCache) dataCache.savedBs = savedBs;
  return savedBs;
}

// ── Routes ───────────────────────────────────────────────────────────────────

app.use(express.json());

/** Single round-trip: 12 Storage exports in parallel (~one slow job, one HTTP). */
app.get('/api/data', async (req, res) => {
  try {
    const payload = await getCachedPayload();
    res.json(payload);
  } catch (err) {
    console.error('api/data error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/static-data', async (req, res) => {
  try {
    const payload = await getCachedPayload();
    res.json(staticSlice(payload));
  } catch (err) {
    console.error('static-data error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/dynamic-data', async (req, res) => {
  try {
    let actVersion = req.query.actVersion;
    let prevVersion = req.query.prevVersion;
    if (prevVersion === '' || prevVersion === undefined) prevVersion = null;

    if (actVersion == null || actVersion === '') {
      const payload = await getCachedPayload();
      actVersion = payload.actVersion;
      prevVersion = payload.prevVersion;
    }

    const data = await loadDynamicData(actVersion, prevVersion);
    res.json(data);
  } catch (err) {
    console.error('dynamic-data error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/save-form', async (req, res) => {
  try {
    const { userId, cc, actVersion, status, rows } = req.body;

    const now = nowSk();
    const df = rows.map((row) => ({
      USER_ID: String(userId).trim(),
      CC: String(cc).trim(),
      BL: row.bl,
      TXT_BUS_LINE: row.txtBusLine || '',
      RAT_BL: String(num(row.ratBl)).replace('.', ','),
      DOM_ABC_PROD: row.product,
      RAT_PROD: String(num(row.ratProd)).replace('.', ','),
      GPM_HIER: row.transType,
      RAT_ACTIVITY: String(num(row.ratActivity)).replace('.', ','),
      TXT_CHANNEL: row.channel,
      RAT_CHANNEL: String(num(row.ratChannel)).replace('.', ','),
      SUBSEGMENT: row.subsegment || '',
      RAT_TOTAL: String(num(row.ratTotal)).replace('.', ','),
      VERSION: String(actVersion),
      STATUS: status,
      FILL_DATE: now,
    }));

    await importTable(TABLES.saved_forms, df, { incremental: true });
    const savedForms = await mergeSavedFormsIntoCache(actVersion);
    res.json({ ok: true, savedForms });
  } catch (err) {
    console.error('save-form error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/save-bs', async (req, res) => {
  try {
    const { userId, cc, actVersion, allocations } = req.body;

    const now = nowSk();
    const df = allocations.map((a) => ({
      USER_ID: String(userId).trim(),
      BL: a.bl,
      TXT_BUS_LINE: a.txtBusLine || '',
      SUBSEGMENT: a.subsegment || '',
      COST_CENTER: String(cc).trim(),
      RAT_TOTAL: String(num(a.ratTotal)).replace('.', ','),
      VERSION: String(actVersion),
      STATUS: 'Submitted',
      FILL_DATE: now,
    }));

    await importTable(TABLES.saved_bs, df, { incremental: true });
    const savedBs = await mergeSavedBsIntoCache(actVersion);
    res.json({ ok: true, savedBs });
  } catch (err) {
    console.error('save-bs error:', err);
    res.status(500).json({ error: err.message });
  }
});

const distDir = path.join(__dirname, 'dist');
app.use(express.static(distDir));
app.all('*', (req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`ABC Dotazník server running on port ${PORT}`);
  if (kbcReadDebug()) {
    console.log('[Keboola read] Debug logging on (per-table + batch timing). Set DEBUG_KBC=0 to disable.');
  }
});
