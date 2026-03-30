// ── Mask helpers ─────────────────────────────────────────────────────────────

export function applyProductMask(displayName, prodMaskOrder) {
  const row = prodMaskOrder.find((r) => r.DOM_ABC_PRD_MASK === displayName);
  return row?.DOM_ABC_PRD || displayName;
}

export function removeProductMask(internalName, prodMaskOrder) {
  const row = prodMaskOrder.find((r) => r.DOM_ABC_PRD === internalName);
  return row?.DOM_ABC_PRD_MASK || internalName;
}

export function applyChannelMask(displayName, channelMaskOrder) {
  const row = channelMaskOrder.find((r) => r.CHANNEL_ABC_MASK === displayName);
  return row?.CHANNEL_ABC || displayName;
}

export function removeChannelMask(internalName, channelMaskOrder) {
  const row = channelMaskOrder.find((r) => r.CHANNEL_ABC === internalName);
  return row?.CHANNEL_ABC_MASK || internalName;
}

// ── Hierarchy ─────────────────────────────────────────────────────────────────

export function buildHierarchy(transData) {
  const blToProducts = {};
  const productToTransTypes = {};
  const transTypeToChannels = {};

  for (const row of transData) {
    const bl = (row.BL || '').trim();
    const product = (row.PRODUCT || '').trim();
    const transType = (row.TRANS_TYPE || '').trim();
    const channel = (row.CHANNEL || '').trim();

    if (!bl || !product || !transType || !channel) continue;

    if (!blToProducts[bl]) blToProducts[bl] = new Set();
    blToProducts[bl].add(product);

    const pk = `${bl}|||${product}`;
    if (!productToTransTypes[pk]) productToTransTypes[pk] = new Set();
    productToTransTypes[pk].add(transType);

    const tk = `${bl}|||${product}|||${transType}`;
    if (!transTypeToChannels[tk]) transTypeToChannels[tk] = new Set();
    transTypeToChannels[tk].add(channel);
  }

  return { blToProducts, productToTransTypes, transTypeToChannels };
}

export function getSortedBls(blOrder, transData) {
  const allBls = [...new Set(transData.map((r) => (r.BL || '').trim()).filter(Boolean))];
  return allBls
    .map((bl) => {
      const meta = blOrder.find((r) => r.BL === bl) || {};
      const group = meta.TXT_BUS_LINE || '';
      const label = group && group.trim() !== bl ? `${group} - ${bl}` : bl;
      return {
        bl,
        label,
        order: parseFloat(meta.BL_ORDER) || 999,
        tooltip: meta.TOOLTIP || '',
        txtBusLine: group,
        subsegment: meta.SUBSEGMENT || '',
      };
    })
    .sort((a, b) => a.order - b.order);
}

export function getSortedProducts(hierarchy, blOrderSorted, prodMaskOrder, bl) {
  const products = [...(hierarchy.blToProducts[bl] || [])];
  return products
    .map((p) => {
      const meta = prodMaskOrder.find((r) => r.DOM_ABC_PRD_MASK === p) || {};
      return {
        name: p,
        order: parseFloat(meta.PROD_ORDER) || 999,
        tooltip: meta.TOOLTIP || '',
      };
    })
    .sort((a, b) => a.order - b.order);
}

export function getSortedTransTypes(hierarchy, gpmOrder, bl, product) {
  const key = `${bl}|||${product}`;
  const types = [...(hierarchy.productToTransTypes[key] || [])];
  return types
    .map((t) => {
      const meta = gpmOrder.find((r) => r.GPM_HIER === t) || {};
      return {
        name: t,
        order: parseFloat(meta.GPM_ORDER) || 999,
        tooltip: meta.TOOLTIP || '',
      };
    })
    .sort((a, b) => a.order - b.order);
}

export function getSortedChannels(hierarchy, channelMaskOrder, bl, product, transType) {
  const key = `${bl}|||${product}|||${transType}`;
  const channels = [...(hierarchy.transTypeToChannels[key] || [])];
  return channels
    .map((c) => {
      const meta = channelMaskOrder.find((r) => r.CHANNEL_ABC_MASK === c) || {};
      return {
        name: c,
        order: parseFloat(meta.CHANNEL_ORDER) || 999,
        tooltip: meta.TOOLTIP || '',
      };
    })
    .sort((a, b) => a.order - b.order);
}

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_LEVEL = { Step1: 1, Step2: 2, Step3: 3, Submitted: 4 };
export function statusLevel(s) { return STATUS_LEVEL[s] || 0; }

export function getMaxStatus(savedForms, cc, version) {
  const rows = savedForms.filter(
    (r) =>
      String(r.CC || '').trim() === String(cc).trim() &&
      String(r.VERSION || '').trim() === String(version).trim()
  );
  if (!rows.length) return '';
  return rows.reduce((best, r) => {
    return statusLevel(r.STATUS) > statusLevel(best) ? r.STATUS : best;
  }, '');
}

export function getFormStatus(savedForms, cc, version) {
  const row = savedForms.find(
    (r) =>
      String(r.CC || '').trim() === String(cc).trim() &&
      String(r.VERSION || '').trim() === String(version).trim()
  );
  return row?.STATUS || '';
}

// ── Pre-populate selections from saved data ───────────────────────────────────

export function loadSelectionsFromRows(rows, prodMaskOrder, channelMaskOrder) {
  const selectedBls = {};
  const selectedProducts = {};
  const selectedTransTypes = {};
  const selectedChannels = {};

  for (const row of rows) {
    const bl = (row.BL || '').trim();
    const product = (row.DOM_ABC_PROD || '').trim();
    const transType = (row.GPM_HIER || '').trim();
    const channel = (row.TXT_CHANNEL || '').trim();

    const ratBl = parseFloat(String(row.RAT_BL || '0').replace(',', '.')) || 0;
    const ratProd = parseFloat(String(row.RAT_PROD || '0').replace(',', '.')) || 0;
    const ratAct = parseFloat(String(row.RAT_ACTIVITY || '0').replace(',', '.')) || 0;
    const ratChan = parseFloat(String(row.RAT_CHANNEL || '0').replace(',', '.')) || 0;

    if (bl && ratBl > 0) selectedBls[bl] = ratBl;

    if (bl && product && ratProd > 0) {
      const displayProduct = removeProductMask(product, prodMaskOrder);
      selectedProducts[`${bl}|||${displayProduct}`] = ratProd;
    }

    if (bl && product && transType && ratAct > 0) {
      const displayProduct = removeProductMask(product, prodMaskOrder);
      selectedTransTypes[`${bl}|||${displayProduct}|||${transType}`] = ratAct;
    }

    if (bl && product && transType && channel && ratChan > 0) {
      const displayProduct = removeProductMask(product, prodMaskOrder);
      const displayChannel = removeChannelMask(channel, channelMaskOrder);
      selectedChannels[`${bl}|||${displayProduct}|||${transType}|||${displayChannel}`] = ratChan;
    }
  }

  return { selectedBls, selectedProducts, selectedTransTypes, selectedChannels };
}
