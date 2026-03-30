import { fmtNum } from '../utils/format';

export default function StepBSSummary({ staticData, state, onBack }) {
  const { fteData } = staticData;
  const { cc, ccDesc, selectedBls } = state;

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const results = Object.entries(selectedBls).map(([bl, ratTotal]) => ({
    bl,
    allocPct: fmtNum(ratTotal, 1),
    fte: fmtNum(totalFte ? (ratTotal / 100) * totalFte : 0, 2),
    _ratTotal: ratTotal,
    _fte: totalFte ? (ratTotal / 100) * totalFte : 0,
  }));

  const handleDownload = () => {
    const header = ['Business Line', 'Alokácia (%)', 'FTE'].join(';');
    const rows = results.map((r) =>
      [r.bl, fmtNum(r._ratTotal, 1), fmtNum(r._fte, 2)].join(';')
    );
    const csv = [header, ...rows].join('\r\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const name = ccDesc ? `BS_dotaznik_${cc}_${ccDesc}` : `BS_dotaznik_${cc}`;
    a.href = url;
    a.download = `${name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="card">
      <h2>✅ Zhrnutie alokácie</h2>
      <div className="msg msg-success">Všetky alokácie boli úspešne zadané!</div>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>← Späť</button>
      </div>

      <h3 style={{ marginBottom: 12 }}>Výsledná alokácia</h3>

      <table className="summary-table">
        <thead>
          <tr>
            <th>Business Line</th>
            <th>Alokácia (%)</th>
            <th>FTE</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i}>
              <td>{r.bl}</td>
              <td>{r.allocPct}</td>
              <td>{r.fte}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 20 }}>
        <button className="btn-primary" onClick={handleDownload}>
          📥 Stiahnuť výsledky CSV
        </button>
      </div>
    </div>
  );
}
