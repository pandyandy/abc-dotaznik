import { useState } from 'react';
import {
  getSortedBls,
  getSortedProducts,
  getSortedTransTypes,
  applyProductMask,
  statusLevel,
} from '../utils/hierarchy';
import { fmtNum } from '../utils/format';

export default function StepActivities({
  staticData,
  dynamicData,
  state,
  hierarchy,
  onBack,
  onNext,
  onSave,
}) {
  const { blOrder, fteData, prodMaskOrder, gpmOrder, trxCount, actVersion, prevVersion } = staticData;
  const {
    cc,
    selectedBls,
    selectedProducts,
    selectedTransTypes: initTT,
    currentStatusSnapshot,
  } = state;

  const useCurrentVersion = statusLevel(currentStatusSnapshot) >= statusLevel('Step3');

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const blMeta = blOrder.reduce((m, r) => { m[r.BL] = r; return m; }, {});

  const getSavedActAlloc = (bl, maskedProd, transType) => {
    const source = (dynamicData?.savedForms || []).filter(
      (r) =>
        String(r.CC || '').trim() === String(cc).trim() &&
        String(r.VERSION || '').trim() ===
          String(useCurrentVersion ? actVersion : prevVersion || '').trim()
    );
    const row = source.find(
      (r) => r.BL === bl && r.DOM_ABC_PROD === maskedProd && r.GPM_HIER === transType
    );
    return row ? parseFloat(String(row.RAT_ACTIVITY || '0').replace(',', '.')) || 0 : 0;
  };

  // Build extended tooltip from trxCount
  const getTooltip = (baseTooltip, bl, product, transType) => {
    const blRow = blOrder.find((r) => r.BL === bl) || {};
    const prodRow = prodMaskOrder.find((r) => r.DOM_ABC_PRD_MASK === product) || {};
    const domProd = prodRow.DOM_ABC_PRD || product;
    const txtBusLine = blRow.TXT_BUS_LINE || '';
    const subsegment = blRow.SUBSEGMENT || '';

    const matching = trxCount.filter(
      (r) =>
        String(r.TXT_BUS_LINE || '').trim() === txtBusLine.trim() &&
        String(r.SUBSEGMENT || '').trim() === subsegment.trim() &&
        String(r.DOM_ABC_PROD || '').trim() === domProd.trim() &&
        String(r.GPM_HIER || '').trim() === transType.trim()
    );

    if (!matching.length && !baseTooltip) return '';

    const lines = [];
    if (baseTooltip) lines.push(baseTooltip);
    if (matching.length) {
      lines.push('Transakcie:');
      const grouped = {};
      for (const r of matching) {
        const desc = String(r.TXT_TRANS_DESC || '').slice(6) || r.TXT_TRANS_DESC;
        const fc = parseFloat(String(r.FC || '0').replace(',', '.')) || 0;
        grouped[desc] = (grouped[desc] || 0) + fc;
      }
      for (const [desc, fc] of Object.entries(grouped)) {
        const fcFmt = fc >= 1000 ? Math.round(fc).toLocaleString('sk-SK') : String(Math.round(fc));
        lines.push(`  ${desc}: ${fcFmt}`);
      }
    }
    return lines.join('\n');
  };

  // Determine sorted products (with BL ordering)
  const sortedEntries = () => {
    const blOrderMap = Object.fromEntries(
      getSortedBls(blOrder, staticData.transData).map((b, i) => [b.bl, i])
    );
    const prodOrderMap = Object.fromEntries(
      prodMaskOrder.map((r) => [r.DOM_ABC_PRD_MASK, parseFloat(r.PROD_ORDER) || 999])
    );
    return Object.keys(selectedProducts)
      .map((key) => {
        const [bl, product] = key.split('|||');
        return { bl, product, key, blOrd: blOrderMap[bl] ?? 999, prodOrd: prodOrderMap[product] ?? 999 };
      })
      .sort((a, b) => a.blOrd - b.blOrd || a.prodOrd - b.prodOrd);
  };

  const initState = () => {
    const checked = {};
    const allocs = {};
    for (const { bl, product } of sortedEntries()) {
      const maskedProd = applyProductMask(product, prodMaskOrder);
      const types = getSortedTransTypes(hierarchy, gpmOrder, bl, product);
      for (const t of types) {
        const key = `${bl}|||${product}|||${t.name}`;
        const savedAlloc = getSavedActAlloc(bl, maskedProd, t.name);
        checked[key] = key in initTT || savedAlloc > 0;
        allocs[key] = key in initTT ? initTT[key] : savedAlloc;
      }
    }
    return { checked, allocs };
  };

  const [{ checked, allocs }, setData] = useState(initState);

  const handleCheck = (key) =>
    setData((d) => ({ ...d, checked: { ...d.checked, [key]: !d.checked[key] } }));
  const handleAlloc = (key, val) =>
    setData((d) => ({ ...d, allocs: { ...d.allocs, [key]: parseFloat(val) || 0 } }));

  // Validate per (bl, product)
  let allValid = true;
  const prodTotals = {};
  for (const { bl, product } of sortedEntries()) {
    const types = getSortedTransTypes(hierarchy, gpmOrder, bl, product);
    const selected = types.filter((t) => checked[`${bl}|||${product}|||${t.name}`]);
    const total = selected.reduce(
      (s, t) => s + (parseFloat(allocs[`${bl}|||${product}|||${t.name}`]) || 0),
      0
    );
    prodTotals[`${bl}|||${product}`] = { total, count: selected.length };
    if (selected.length === 0 || Math.abs(total - 100) > 0.01) allValid = false;
  }

  const handleNext = () => {
    const selectedTransTypes = {};
    for (const { bl, product } of sortedEntries()) {
      const types = getSortedTransTypes(hierarchy, gpmOrder, bl, product);
      for (const t of types) {
        const key = `${bl}|||${product}|||${t.name}`;
        if (checked[key]) selectedTransTypes[key] = allocs[key] || 0;
      }
    }

    const rows = [];
    for (const [key, ratActivity] of Object.entries(selectedTransTypes)) {
      const [bl, product, transType] = key.split('|||');
      if (ratActivity <= 0) continue;
      const maskedProd = applyProductMask(product, prodMaskOrder);
      rows.push({
        bl,
        txtBusLine: blMeta[bl]?.TXT_BUS_LINE || '',
        subsegment: blMeta[bl]?.SUBSEGMENT || '',
        ratBl: selectedBls[bl] || 0,
        product: maskedProd,
        ratProd: selectedProducts[`${bl}|||${product}`] || 0,
        transType,
        ratActivity,
        channel: '',
        ratChannel: 0,
        ratTotal: 0,
      });
    }

    onSave(rows, 'Step3');
    onNext(selectedTransTypes);
  };

  return (
    <div className="card">
      <h2>Krok 3: Výber aktivity</h2>
      <p className="card-desc">
        Pre každý vybraný produkt vyberte všetky aktivity a rozdeľte alokáciu (celkom 100% pre každý produkt).
      </p>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>← Späť</button>
      </div>

      {sortedEntries().map(({ bl, product }) => {
        const blAlloc = selectedBls[bl] || 0;
        const prodAlloc = selectedProducts[`${bl}|||${product}`] || 0;
        const fte = totalFte ? (blAlloc / 100) * (prodAlloc / 100) * totalFte : null;
        const types = getSortedTransTypes(hierarchy, gpmOrder, bl, product);
        const { total, count } = prodTotals[`${bl}|||${product}`] || { total: 0, count: 0 };
        const sectionValid = count > 0 && Math.abs(total - 100) <= 0.01;
        const blLabel = blOrder.find((r) => r.BL === bl)?.TXT_BUS_LINE || bl;

        return (
          <div key={`${bl}|||${product}`}>
            <div className="section-header">
              {blLabel} ({fmtNum(blAlloc, 0)}%) — {product} ({fmtNum(prodAlloc, 0)}%)
              {fte !== null && ` — ${fmtNum(fte, 2)} FTEs`}
            </div>

            <table className="alloc-table">
              <thead>
                <tr>
                  <th className="col-name">Aktivita</th>
                  <th className="col-alloc">Alokácia (%)</th>
                  <th className="col-fte">FTEs</th>
                </tr>
              </thead>
              <tbody>
                {types.map((t) => {
                  const key = `${bl}|||${product}|||${t.name}`;
                  const isChecked = checked[key];
                  const alloc = parseFloat(allocs[key]) || 0;
                  const ttFte =
                    totalFte && isChecked
                      ? (blAlloc / 100) * (prodAlloc / 100) * (alloc / 100) * totalFte
                      : null;
                  const tooltip = getTooltip(t.tooltip, bl, product, t.name);
                  return (
                    <tr key={key}>
                      <td>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleCheck(key)}
                          />
                          <span title={tooltip || undefined}>{t.name}</span>
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
                      <td>{ttFte !== null ? fmtNum(ttFte, 2) : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="total-row">
              <span className="total-label">Celková alokácia pre {product}:</span>
              <span className={`total-value ${sectionValid ? 'total-ok' : 'total-bad'}`}>
                {fmtNum(total, 1)}%
              </span>
            </div>

            {count === 0 && (
              <div className="msg msg-warning">⚠️ Musíte vybrať aspoň jednu aktivitu pre {product}</div>
            )}
            {count > 0 && !sectionValid && (
              <div className="msg msg-error">
                ⚠️ Alokácia pre {product} musí byť presne 100%. Aktuálne: {fmtNum(total, 1)}%
              </div>
            )}

            <hr className="divider" />
          </div>
        );
      })}

      <button className="btn-primary" disabled={!allValid} onClick={handleNext}>
        Ďalej →
      </button>
    </div>
  );
}
