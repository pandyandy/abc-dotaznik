import { useState, useEffect } from 'react';
import { getSortedBls, applyProductMask } from '../utils/hierarchy';
import { fmtNum } from '../utils/format';

export default function StepBL({ staticData, state, hierarchy, onBack, onNext, onSave }) {
  const { blOrder, fteData, actVersion } = staticData;
  const { cc, selectedBls: initBls } = state;

  const sortedBls = getSortedBls(blOrder, staticData.transData);

  const [checked, setChecked] = useState(() => {
    const init = {};
    for (const b of sortedBls) init[b.bl] = b.bl in initBls;
    return init;
  });
  const [allocs, setAllocs] = useState(() => ({ ...initBls }));

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const selectedList = sortedBls.filter((b) => checked[b.bl]);
  const total = selectedList.reduce((s, b) => s + (parseFloat(allocs[b.bl]) || 0), 0);
  const totalOk = selectedList.length > 0 && Math.abs(total - 100) <= 0.01;

  const handleCheck = (bl) => {
    setChecked((c) => ({ ...c, [bl]: !c[bl] }));
    if (!checked[bl] && !(bl in allocs)) {
      setAllocs((a) => ({ ...a, [bl]: 0 }));
    }
  };

  const handleAlloc = (bl, val) => {
    setAllocs((a) => ({ ...a, [bl]: parseFloat(val) || 0 }));
  };

  const handleNext = () => {
    const selectedBls = {};
    for (const b of selectedList) selectedBls[b.bl] = allocs[b.bl] || 0;

    // Build save rows (Step1 – no product/activity/channel yet)
    const blMeta = blOrder.reduce((m, r) => { m[r.BL] = r; return m; }, {});
    const rows = Object.entries(selectedBls).map(([bl, ratBl]) => ({
      bl,
      txtBusLine: blMeta[bl]?.TXT_BUS_LINE || '',
      subsegment: blMeta[bl]?.SUBSEGMENT || '',
      ratBl,
      product: '',
      ratProd: 0,
      transType: '',
      ratActivity: 0,
      channel: '',
      ratChannel: 0,
      ratTotal: 0,
    }));

    onSave(rows, 'Step1');
    onNext(selectedBls);
  };

  return (
    <div className="card">
      <h2>Krok 1: Výber biznis línií a segmentov</h2>
      <p className="card-desc">
        Vyberte všetky biznis línie a segmenty, v ktorých je vaše oddelenie aktívne,
        a rozdeľte medzi nimi alokáciu (celkom 100%).
      </p>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>🔄 Zmeniť údaje</button>
      </div>

      <table className="alloc-table">
        <thead>
          <tr>
            <th className="col-name">Názov</th>
            <th className="col-alloc">Alokácia (%)</th>
            <th className="col-fte">FTEs</th>
          </tr>
        </thead>
        <tbody>
          {sortedBls.map((b) => {
            const isChecked = checked[b.bl];
            const alloc = parseFloat(allocs[b.bl]) || 0;
            const fte = totalFte ? (alloc / 100) * totalFte : null;
            return (
              <tr key={b.bl}>
                <td>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleCheck(b.bl)}
                    />
                    <span title={b.tooltip || undefined}>{b.label}</span>
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
                      value={allocs[b.bl] ?? ''}
                      onChange={(e) => handleAlloc(b.bl, e.target.value)}
                    />
                  )}
                </td>
                <td>
                  {isChecked && fte !== null ? fmtNum(fte, 2) : ''}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <hr className="divider" />
      <div className="total-row">
        <span className="total-label">Celková alokácia:</span>
        <span className={`total-value ${totalOk ? 'total-ok' : 'total-bad'}`}>
          {fmtNum(total, 1)}%
        </span>
      </div>

      {!totalOk && selectedList.length > 0 && (
        <div className="msg msg-error">
          ⚠️ Celková alokácia musí byť presne 100%. Aktuálne: {fmtNum(total, 1)}%
        </div>
      )}
      {selectedList.length === 0 && (
        <div className="msg msg-warning">Vyberte aspoň jednu biznis líniu.</div>
      )}

      <button
        className="btn-primary"
        disabled={!totalOk}
        onClick={handleNext}
      >
        Ďalej →
      </button>
    </div>
  );
}
