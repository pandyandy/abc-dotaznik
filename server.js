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

// ── In-memory cache (5 min TTL) ──────────────────────────────────────────────
let staticCache = null;
let staticCacheTime = 0;
const CACHE_TTL = 5 * 60 * 1000;

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

// ── Data helpers ─────────────────────────────────────────────────────────────

async function loadStaticData() {
  if (staticCache && Date.now() - staticCacheTime < CACHE_TTL) return staticCache;

  const [rawVersion, rawTransData, rawFteData, rawBlOrder, rawGpmOrder,
    rawProdMask, rawChannelMask, rawCcDesc, rawTrxCount] = await Promise.all([
    exportTable(TABLES.version),
    exportTable(TABLES.trans_data),
    exportTable(TABLES.fte_data),
    exportTable(TABLES.bl_order),
    exportTable(TABLES.gpm_order),
    exportTable(TABLES.prod_mask_order),
    exportTable(TABLES.channel_mask_order),
    exportTable(TABLES.cc_desc),
    exportTable(TABLES.trx_count),
  ]);

  // Determine active/previous version
  const versionsSorted = [...rawVersion].sort((a, b) =>
    parseInt(b.VERSION_ID) - parseInt(a.VERSION_ID)
  );
  const actVersionRow = versionsSorted[0];
  const prevVersionRow = versionsSorted[1] || null;
  const actVersion = actVersionRow?.VERSION || '';
  const prevVersion = prevVersionRow?.VERSION || null;

  // Filter trans_data: version flag == 'act' AND VERSION matches actVersion
  const transData = rawTransData.filter(
    (r) =>
      String(r.VERSION || r.version || '').trim() === String(actVersion).trim() ||
      String(r.version || '').toLowerCase().trim() === 'act'
  );

  // Filter trxCount: version == 'act'
  const trxCount = rawTrxCount.filter(
    (r) => String(r.version || r.VERSION || '').toLowerCase().trim() === 'act'
  );

  staticCache = {
    transData,
    fteData: rawFteData,
    blOrder: rawBlOrder,
    gpmOrder: rawGpmOrder,
    prodMaskOrder: rawProdMask,
    channelMaskOrder: rawChannelMask,
    ccDesc: rawCcDesc,
    trxCount,
    actVersion,
    prevVersion,
    versions: rawVersion,
  };
  staticCacheTime = Date.now();
  return staticCache;
}

async function loadDynamicData(actVersion, prevVersion) {
  const [rawCcUser, rawSavedForms, rawSavedBs] = await Promise.all([
    exportTable(TABLES.cc_user),
    exportTable(TABLES.saved_forms),
    exportTable(TABLES.saved_bs),
  ]);

  const validVersions = [String(actVersion)];
  if (prevVersion) validVersions.push(String(prevVersion));

  const savedForms = rawSavedForms.filter((r) =>
    validVersions.includes(String(r.VERSION || '').trim())
  );
  const savedBs = rawSavedBs.filter((r) =>
    validVersions.includes(String(r.VERSION || '').trim())
  );

  return { ccUser: rawCcUser, savedForms, savedBs };
}

// ── Routes ───────────────────────────────────────────────────────────────────

app.use(express.json());

app.get('/api/static-data', async (req, res) => {
  try {
    const data = await loadStaticData();
    res.json(data);
  } catch (err) {
    console.error('static-data error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/dynamic-data', async (req, res) => {
  try {
    const { actVersion, prevVersion } = await loadStaticData();
    const data = await loadDynamicData(actVersion, prevVersion);
    res.json(data);
  } catch (err) {
    console.error('dynamic-data error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/save-form
// Body: { userId, cc, actVersion, status, rows: [{ bl, ratBl, product, ratProd, transType, ratActivity, channel, ratChannel, ratTotal }] }
// "rows" already have masked product/channel names (sent from client after applying masks)
app.post('/api/save-form', async (req, res) => {
  try {
    const { userId, cc, actVersion, status, rows, isFirstInStep, blOrderData } = req.body;

    // Load current saved forms
    const { savedForms } = await loadDynamicData(actVersion, null);

    let df = savedForms.filter(
      (r) =>
        String(r.CC || '').trim() !== String(cc).trim() ||
        String(r.VERSION || '').trim() !== String(actVersion).trim()
    );

    // If NOT first in step, keep rows from other BL/PROD/GPM/CHANNEL combos
    // (but since we send all rows at once, we always do a full replace for this CC/VERSION)
    // Full replace for this CC/VERSION:
    const now = nowSk();
    for (const row of rows) {
      df.push({
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
      });
    }

    await importTable(TABLES.saved_forms, df);
    res.json({ ok: true });
  } catch (err) {
    console.error('save-form error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/save-bs
// Body: { userId, cc, actVersion, allocations: [{ bl, txtBusLine, subsegment, ratTotal }] }
app.post('/api/save-bs', async (req, res) => {
  try {
    const { userId, cc, actVersion, allocations } = req.body;

    const { savedBs } = await loadDynamicData(actVersion, null);

    let df = savedBs.filter(
      (r) =>
        String(r.COST_CENTER || '').trim() !== String(cc).trim() ||
        String(r.VERSION || '').trim() !== String(actVersion).trim()
    );

    const now = nowSk();
    for (const a of allocations) {
      df.push({
        USER_ID: String(userId).trim(),
        BL: a.bl,
        TXT_BUS_LINE: a.txtBusLine || '',
        SUBSEGMENT: a.subsegment || '',
        COST_CENTER: String(cc).trim(),
        RAT_TOTAL: String(num(a.ratTotal)).replace('.', ','),
        VERSION: String(actVersion),
        STATUS: 'Submitted',
        FILL_DATE: now,
      });
    }

    await importTable(TABLES.saved_bs, df);
    res.json({ ok: true });
  } catch (err) {
    console.error('save-bs error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Serve React build (production) ───────────────────────────────────────────
const distDir = path.join(__dirname, 'dist');
app.use(express.static(distDir));
app.all('*', (req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`ABC Dotazník server running on port ${PORT}`);
});
