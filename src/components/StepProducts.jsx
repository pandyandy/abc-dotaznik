import { useState } from 'react';
import {
  getSortedBls,
  getSortedProducts,
  applyProductMask,
  statusLevel,
} from '../utils/hierarchy';
import { fmtNum } from '../utils/format';

export default function StepProducts({
  staticData,
  dynamicData,
  state,
  hierarchy,
  onBack,
  onNext,
  onSave,
}) {
  const { blOrder, fteData, prodMaskOrder, actVersion, prevVersion } = staticData;
  const { cc, selectedBls, selectedProducts: initProducts, currentStatusSnapshot } = state;

  const useCurrentVersion = statusLevel(currentStatusSnapshot) >= statusLevel('Step2');

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const blMeta = blOrder.reduce((m, r) => { m[r.BL] = r; return m; }, {});

  // Sort BLs by order
  const sortedBls = getSortedBls(blOrder, staticData.transData)
    .filter((b) => b.bl in selectedBls);

  // Helper: get saved allocation for product
  const getSavedProdAlloc = (bl, maskedProduct) => {
    const source = useCurrentVersion
      ? (dynamicData?.savedForms || []).filter(
          (r) =>
            String(r.CC || '').trim() === String(cc).trim() &&
            String(r.VERSION || '').trim() === String(actVersion).trim()
        )
      : (dynamicData?.savedForms || []).filter(
          (r) =>
            String(r.CC || '').trim() === String(cc).trim() &&
            String(r.VERSION || '').trim() === String(prevVersion || '').trim()
        );
    const row = source.find((r) => r.BL === bl && r.DOM_ABC_PROD === maskedProduct);
    return row ? parseFloat(String(row.RAT_PROD || '0').replace(',', '.')) || 0 : 0;
  };

  // Build initial state for each BL section
  const initState = () => {
    const checked = {};
    const allocs = {};
    for (const { bl } of sortedBls) {
      const products = getSortedProducts(hierarchy, blOrder, prodMaskOrder, bl);
      for (const p of products) {
        const key = `${bl}|||${p.name}`;
        const maskedProd = applyProductMask(p.name, prodMaskOrder);
        const fromParent = `${bl}|||${p.name}` in initProducts;
        const savedAlloc = getSavedProdAlloc(bl, maskedProd);
        checked[key] = fromParent || savedAlloc > 0;
        allocs[key] = fromParent
          ? initProducts[`${bl}|||${p.name}`]
          : savedAlloc;
      }
    }
    return { checked, allocs };
  };

  const [{ checked, allocs }, setData] = useState(initState);

  const handleCheck = (key) =>
    setData((d) => ({ ...d, checked: { ...d.checked, [key]: !d.checked[key] } }));

  const handleAlloc = (key, val) =>
    setData((d) => ({ ...d, allocs: { ...d.allocs, [key]: parseFloat(val) || 0 } }));

  // Validate all BLs
  let allValid = true;
  const blTotals = {};
  for (const { bl } of sortedBls) {
    const products = getSortedProducts(hierarchy, blOrder, prodMaskOrder, bl);
    const selected = products.filter((p) => checked[`${bl}|||${p.name}`]);
    const total = selected.reduce((s, p) => s + (parseFloat(allocs[`${bl}|||${p.name}`]) || 0), 0);
    blTotals[bl] = { total, count: selected.length };
    if (selected.length === 0 || Math.abs(total - 100) > 0.01) allValid = false;
  }

  const handleNext = () => {
    const selectedProducts = {};
    for (const { bl } of sortedBls) {
      const products = getSortedProducts(hierarchy, blOrder, prodMaskOrder, bl);
      for (const p of products) {
        const key = `${bl}|||${p.name}`;
        if (checked[key]) selectedProducts[key] = allocs[key] || 0;
      }
    }

    const rows = [];
    for (const [key, ratProd] of Object.entries(selectedProducts)) {
      const [bl, product] = key.split('|||');
      if (ratProd <= 0) continue;
      const maskedProd = applyProductMask(product, prodMaskOrder);
      rows.push({
        bl,
        txtBusLine: blMeta[bl]?.TXT_BUS_LINE || '',
        subsegment: blMeta[bl]?.SUBSEGMENT || '',
        ratBl: selectedBls[bl] || 0,
        product: maskedProd,
        ratProd,
        transType: '',
        ratActivity: 0,
        channel: '',
        ratChannel: 0,
        ratTotal: 0,
      });
    }

    onSave(rows, 'Step2');
    onNext(selectedProducts);
  };

  return (
    <div className="card">
      <h2>Krok 2: Výber produktov</h2>
      <p className="card-desc">
        Pre každú vybranú biznis líniu vyberte všetky produkty a rozdeľte alokáciu (celkom 100% pre každú BL).
      </p>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>← Späť</button>
      </div>

      {sortedBls.map(({ bl, label }) => {
        const blAlloc = selectedBls[bl] || 0;
        const blFte = totalFte ? (blAlloc / 100) * totalFte : null;
        const products = getSortedProducts(hierarchy, blOrder, prodMaskOrder, bl);
        const { total, count } = blTotals[bl] || { total: 0, count: 0 };
        const blValid = count > 0 && Math.abs(total - 100) <= 0.01;

        return (
          <div key={bl}>
            <div className="section-header">
              {label} ({fmtNum(blAlloc, 0)}%)
              {blFte !== null && ` — ${fmtNum(blFte, 2)} FTEs`}
            </div>

            <table className="alloc-table">
              <thead>
                <tr>
                  <th className="col-name">Produkt</th>
                  <th className="col-alloc">Alokácia (%)</th>
                  <th className="col-fte">FTEs</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const key = `${bl}|||${p.name}`;
                  const isChecked = checked[key];
                  const alloc = parseFloat(allocs[key]) || 0;
                  const fte =
                    totalFte && isChecked
                      ? (blAlloc / 100) * (alloc / 100) * totalFte
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
                          <span title={p.tooltip || undefined}>{p.name}</span>
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
                      <td>{fte !== null ? fmtNum(fte, 2) : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="total-row">
              <span className="total-label">Celková alokácia pre {bl}:</span>
              <span className={`total-value ${blValid ? 'total-ok' : 'total-bad'}`}>
                {fmtNum(total, 1)}%
              </span>
            </div>

            {count === 0 && (
              <div className="msg msg-warning">⚠️ Musíte vybrať aspoň jeden produkt pre {bl}</div>
            )}
            {count > 0 && !blValid && (
              <div className="msg msg-error">
                ⚠️ Alokácia pre {bl} musí byť presne 100%. Aktuálne: {fmtNum(total, 1)}%
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
