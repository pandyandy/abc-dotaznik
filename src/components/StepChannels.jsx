import { useState } from 'react';
import {
  getSortedBls,
  getSortedTransTypes,
  getSortedChannels,
  applyProductMask,
  applyChannelMask,
  statusLevel,
} from '../utils/hierarchy';
import { fmtNum } from '../utils/format';

export default function StepChannels({
  staticData,
  dynamicData,
  state,
  saving,
  hierarchy,
  onBack,
  onNext,
  onSave,
}) {
  const { blOrder, fteData, prodMaskOrder, gpmOrder, channelMaskOrder, actVersion, prevVersion } =
    staticData;
  const {
    cc,
    selectedBls,
    selectedProducts,
    selectedTransTypes,
    selectedChannels: initCh,
    currentStatusSnapshot,
  } = state;

  const useCurrentVersion = statusLevel(currentStatusSnapshot) >= statusLevel('Submitted');

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);
  const blMeta = blOrder.reduce((m, r) => { m[r.BL] = r; return m; }, {});

  const getSavedChanAlloc = (bl, maskedProd, transType, maskedChan) => {
    const source = (dynamicData?.savedForms || []).filter(
      (r) =>
        String(r.CC || '').trim() === String(cc).trim() &&
        String(r.VERSION || '').trim() ===
          String(useCurrentVersion ? actVersion : prevVersion || '').trim()
    );
    const row = source.find(
      (r) =>
        r.BL === bl &&
        r.DOM_ABC_PROD === maskedProd &&
        r.GPM_HIER === transType &&
        r.TXT_CHANNEL === maskedChan
    );
    return row ? parseFloat(String(row.RAT_CHANNEL || '0').replace(',', '.')) || 0 : 0;
  };

  // Sorted trans types across all selected products
  const sortedEntries = () => {
    const blOrderMap = Object.fromEntries(
      getSortedBls(blOrder, staticData.transData).map((b, i) => [b.bl, i])
    );
    const prodOrderMap = Object.fromEntries(
      prodMaskOrder.map((r) => [r.DOM_ABC_PRD_MASK, parseFloat(r.PROD_ORDER) || 999])
    );
    const gpmOrderMap = Object.fromEntries(
      gpmOrder.map((r) => [r.GPM_HIER, parseFloat(r.GPM_ORDER) || 999])
    );
    return Object.keys(selectedTransTypes)
      .map((key) => {
        const [bl, product, transType] = key.split('|||');
        return {
          bl, product, transType, key,
          blOrd: blOrderMap[bl] ?? 999,
          prodOrd: prodOrderMap[product] ?? 999,
          gpmOrd: gpmOrderMap[transType] ?? 999,
        };
      })
      .sort((a, b) => a.blOrd - b.blOrd || a.prodOrd - b.prodOrd || a.gpmOrd - b.gpmOrd);
  };

  const initState = () => {
    const checked = {};
    const allocs = {};
    for (const { bl, product, transType } of sortedEntries()) {
      const maskedProd = applyProductMask(product, prodMaskOrder);
      const channels = getSortedChannels(hierarchy, channelMaskOrder, bl, product, transType);
      for (const ch of channels) {
        const key = `${bl}|||${product}|||${transType}|||${ch.name}`;
        const maskedChan = applyChannelMask(ch.name, channelMaskOrder);
        const savedAlloc = getSavedChanAlloc(bl, maskedProd, transType, maskedChan);
        checked[key] = key in initCh || savedAlloc > 0;
        allocs[key] = key in initCh ? initCh[key] : savedAlloc;
      }
    }
    return { checked, allocs };
  };

  const [{ checked, allocs }, setData] = useState(initState);

  const handleCheck = (key) =>
    setData((d) => ({ ...d, checked: { ...d.checked, [key]: !d.checked[key] } }));
  const handleAlloc = (key, val) =>
    setData((d) => ({ ...d, allocs: { ...d.allocs, [key]: parseFloat(val) || 0 } }));

  // Validate per (bl, product, transType)
  let allValid = true;
  const ttTotals = {};
  for (const { bl, product, transType } of sortedEntries()) {
    const channels = getSortedChannels(hierarchy, channelMaskOrder, bl, product, transType);
    const selected = channels.filter(
      (ch) => checked[`${bl}|||${product}|||${transType}|||${ch.name}`]
    );
    const total = selected.reduce(
      (s, ch) =>
        s + (parseFloat(allocs[`${bl}|||${product}|||${transType}|||${ch.name}`]) || 0),
      0
    );
    ttTotals[`${bl}|||${product}|||${transType}`] = { total, count: selected.length };
    if (selected.length === 0 || Math.abs(total - 100) > 0.01) allValid = false;
  }

  const handleNext = async () => {
    const selectedChannels = {};
    for (const { bl, product, transType } of sortedEntries()) {
      const channels = getSortedChannels(hierarchy, channelMaskOrder, bl, product, transType);
      for (const ch of channels) {
        const key = `${bl}|||${product}|||${transType}|||${ch.name}`;
        if (checked[key]) selectedChannels[key] = allocs[key] || 0;
      }
    }

    const rows = [];
    for (const [key, ratChannel] of Object.entries(selectedChannels)) {
      const [bl, product, transType, channel] = key.split('|||');
      if (ratChannel <= 0) continue;
      const maskedProd = applyProductMask(product, prodMaskOrder);
      const maskedChan = applyChannelMask(channel, channelMaskOrder);
      const ratBl = selectedBls[bl] || 0;
      const ratProd = selectedProducts[`${bl}|||${product}`] || 0;
      const ratActivity = selectedTransTypes[`${bl}|||${product}|||${transType}`] || 0;
      const ratTotal = (ratBl * ratProd * ratActivity * ratChannel) / 1_000_000;
      rows.push({
        bl,
        txtBusLine: blMeta[bl]?.TXT_BUS_LINE || '',
        subsegment: blMeta[bl]?.SUBSEGMENT || '',
        ratBl,
        product: maskedProd,
        ratProd,
        transType,
        ratActivity,
        channel: maskedChan,
        ratChannel,
        ratTotal,
      });
    }

    await onSave(rows, 'Submitted');
    onNext(selectedChannels);
  };

  return (
    <div className="card">
      <h2>Krok 4: Výber kanálov</h2>
      <p className="card-desc">
        Pre každú vybranú aktivitu vyberte klientsky kanál a rozdeľte alokáciu (celkom 100% pre každú aktivitu).
      </p>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>← Späť</button>
      </div>

      {sortedEntries().map(({ bl, product, transType }) => {
        const blAlloc = selectedBls[bl] || 0;
        const prodAlloc = selectedProducts[`${bl}|||${product}`] || 0;
        const ttAlloc = selectedTransTypes[`${bl}|||${product}|||${transType}`] || 0;
        const fte = totalFte
          ? (blAlloc / 100) * (prodAlloc / 100) * (ttAlloc / 100) * totalFte
          : null;
        const channels = getSortedChannels(hierarchy, channelMaskOrder, bl, product, transType);
        const { total, count } = ttTotals[`${bl}|||${product}|||${transType}`] || { total: 0, count: 0 };
        const sectionValid = count > 0 && Math.abs(total - 100) <= 0.01;
        const blLabel = blOrder.find((r) => r.BL === bl)?.TXT_BUS_LINE || bl;

        return (
          <div key={`${bl}|||${product}|||${transType}`}>
            <div className="section-header">
              {blLabel} ({fmtNum(blAlloc, 0)}%) — {product} ({fmtNum(prodAlloc, 0)}%) — {transType} ({fmtNum(ttAlloc, 0)}%)
              {fte !== null && ` — ${fmtNum(fte, 2)} FTEs`}
            </div>

            <table className="alloc-table">
              <thead>
                <tr>
                  <th className="col-name">Kanál</th>
                  <th className="col-alloc">Alokácia (%)</th>
                  <th className="col-fte">FTEs</th>
                </tr>
              </thead>
              <tbody>
                {channels.map((ch) => {
                  const key = `${bl}|||${product}|||${transType}|||${ch.name}`;
                  const isChecked = checked[key];
                  const alloc = parseFloat(allocs[key]) || 0;
                  const chFte =
                    totalFte && isChecked
                      ? (blAlloc / 100) *
                        (prodAlloc / 100) *
                        (ttAlloc / 100) *
                        (alloc / 100) *
                        totalFte
                      : null;
                  return (
                    <tr key={key}>
                      <td>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleCheck(key)}
                          />
                          <span title={ch.tooltip || undefined}>{ch.name}</span>
                        </label>
                      </td>
                      <td>
                        {isChecked && (
                          <input
                            type="number"
                            className="alloc-input"
                            min="0"
                            max="100"
                            step="0.1"
                            value={allocs[key] ?? ''}
                            onChange={(e) => handleAlloc(key, e.target.value)}
                          />
                        )}
                      </td>
                      <td>{chFte !== null ? fmtNum(chFte, 2) : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="total-row">
              <span className="total-label">Celková alokácia pre {transType}:</span>
              <span className={`total-value ${sectionValid ? 'total-ok' : 'total-bad'}`}>
                {fmtNum(total, 1)}%
              </span>
            </div>

            {count === 0 && (
              <div className="msg msg-warning">⚠️ Musíte vybrať aspoň jeden kanál pre {transType}</div>
            )}
            {count > 0 && !sectionValid && (
              <div className="msg msg-error">
                ⚠️ Alokácia pre {transType} musí byť presne 100%. Aktuálne: {fmtNum(total, 1)}%
              </div>
            )}

            <hr className="divider" />
          </div>
        );
      })}

      <button className="btn-primary" disabled={!allValid || saving} onClick={handleNext}>
        {saving ? 'Ukladám…' : 'Hotovo'}
      </button>
    </div>
  );
}
