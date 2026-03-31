import { useState } from 'react';
import { getSortedBls } from '../utils/hierarchy';
import { fmtNum } from '../utils/format';

export default function StepBSForm({
  staticData,
  dynamicData,
  state,
  hierarchy,
  onBack,
  onNext,
  onSave,
}) {
  const { blOrder, fteData, actVersion, prevVersion } = staticData;
  const { cc, selectedBls: initBls } = state;

  const sortedBls = getSortedBls(blOrder, staticData.transData);

  // Pre-load from BS saved data
  const getInitAllocs = () => {
    const result = { ...initBls };
    if (!Object.keys(result).length && dynamicData) {
      const savedBs = dynamicData.savedBs || [];
      // Try current version, then prev
      let existing = savedBs.filter(
        (r) =>
          String(r.COST_CENTER || '').trim() === String(cc).trim() &&
          String(r.VERSION || '').trim() === String(actVersion).trim()
      );
      if (!existing.length && prevVersion) {
        existing = savedBs.filter(
          (r) =>
            String(r.COST_CENTER || '').trim() === String(cc).trim() &&
            String(r.VERSION || '').trim() === String(prevVersion).trim()
        );
      }
      for (const row of existing) {
        const bl = (row.BL || '').trim();
        const rat = parseFloat(String(row.RAT_TOTAL || '0').replace(',', '.')) || 0;
        if (bl && rat > 0) result[bl] = rat;
      }
    }
    return result;
  };

  const [checked, setChecked] = useState(() => {
    const init = getInitAllocs();
    const c = {};
    for (const b of sortedBls) c[b.bl] = b.bl in init;
    return c;
  });
  const [allocs, setAllocs] = useState(getInitAllocs);

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const selectedList = sortedBls.filter((b) => checked[b.bl]);
  const total = selectedList.reduce((s, b) => s + (parseFloat(allocs[b.bl]) || 0), 0);
  const totalOk = selectedList.length > 0 && Math.abs(total - 100) <= 0.01;

  const handleCheck = (bl) => {
    setChecked((c) => ({ ...c, [bl]: !c[bl] }));
  };
  const handleAlloc = (bl, val) => {
    setAllocs((a) => ({ ...a, [bl]: parseFloat(val) || 0 }));
  };

  const handleNext = () => {
    const selectedBls = {};
    for (const b of selectedList) selectedBls[b.bl] = allocs[b.bl] || 0;

    const allocations = Object.entries(selectedBls).map(([bl, ratTotal]) => {
      const meta = blOrder.find((r) => r.BL === bl) || {};
      return {
        bl,
        txtBusLine: meta.TXT_BUS_LINE || '',
        subsegment: meta.SUBSEGMENT || '',
        ratTotal,
      };
    });

    onSave(allocations);
    onNext(selectedBls);
  };

  return (
    <div className="card">
      <h2>Výber biznis línií a segmentov</h2>
      <p className="card-desc">
        Vyberte biznis línie a segmenty, ktorým venujete čas a rozdeľte medzi nimi alokáciu (celkom 100%).
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
            const fte = totalFte && isChecked ? (alloc / 100) * totalFte : null;
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
                <td>{fte !== null ? fmtNum(fte, 2) : ''}</td>
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
        Hotovo
      </button>
    </div>
  );
}
