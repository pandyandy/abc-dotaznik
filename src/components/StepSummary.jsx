import { fmtNum } from '../utils/format';

export default function StepSummary({ staticData, state, onBack }) {
  const { fteData } = staticData;
  const { cc, ccDesc, selectedBls, selectedProducts, selectedTransTypes, selectedChannels } = state;

  const fteRow = fteData.find((r) => String(r.CC || '').trim() === String(cc).trim());
  const totalFte = parseFloat(fteRow?.NUM_FTE || 0);

  const results = [];
  let finalTotal = 0;

  for (const [blKey, blAlloc] of Object.entries(selectedBls)) {
    for (const [prodKey, prodAlloc] of Object.entries(selectedProducts)) {
      const [bl2, product] = prodKey.split('|||');
      if (bl2 !== blKey) continue;

      for (const [ttKey, ttAlloc] of Object.entries(selectedTransTypes)) {
        const [bl3, prod3, transType] = ttKey.split('|||');
        if (bl3 !== blKey || prod3 !== product) continue;

        for (const [chKey, chAlloc] of Object.entries(selectedChannels)) {
          const [bl4, prod4, tt4, channel] = chKey.split('|||');
          if (bl4 !== blKey || prod4 !== product || tt4 !== transType) continue;

          const finalAlloc = (blAlloc * prodAlloc * ttAlloc * chAlloc) / 1_000_000;
          finalTotal += finalAlloc;
          const weightedFte =
            (blAlloc / 100) * (prodAlloc / 100) * (ttAlloc / 100) * (chAlloc / 100) * totalFte;

          results.push({
            bl: blKey,
            blPct: fmtNum(blAlloc, 1),
            product,
            prodPct: fmtNum(prodAlloc, 1),
            transType,
            ttPct: fmtNum(ttAlloc, 1),
            channel,
            chPct: fmtNum(chAlloc, 1),
            allocPct: fmtNum(finalAlloc, 4),
            weightedFte: fmtNum(weightedFte, 2),
            // For CSV export (comma decimal)
            _finalAlloc: finalAlloc,
            _weightedFte: weightedFte,
          });
        }
      }
    }
  }

  const handleDownload = () => {
    const header = [
      'Business Line', 'BL (%)', 'Product', 'Product (%)',
      'Aktivita', 'Aktivita (%)', 'Kanál', 'Kanál (%)',
      'Alokácia (%)', 'Weighted FTE',
    ].join(';');

    const rows = results.map((r) =>
      [
        r.bl,
        fmtNum(parseFloat(r.blPct.replace(',', '.')), 1),
        r.product,
        fmtNum(parseFloat(r.prodPct.replace(',', '.')), 1),
        r.transType,
        fmtNum(parseFloat(r.ttPct.replace(',', '.')), 1),
        r.channel,
        fmtNum(parseFloat(r.chPct.replace(',', '.')), 1),
        fmtNum(r._finalAlloc, 4),
        fmtNum(r._weightedFte, 2),
      ].join(';')
    );

    const csv = [header, ...rows].join('\r\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const name = ccDesc ? `ABC_dotaznik_${cc}_${ccDesc}` : `ABC_dotaznik_${cc}`;
    a.href = url;
    a.download = `${name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const { cc: ccVal } = state;

  return (
    <div className="card">
      <h2>✅ Zhrnutie alokácie</h2>
      <div className="msg msg-success">Všetky alokácie boli úspešne zadané!</div>

      <div className="btn-row">
        <button className="btn-secondary" onClick={onBack}>← Späť</button>
      </div>

      <h3 style={{ marginBottom: 12 }}>Výsledná alokácia</h3>

      <div style={{ overflowX: 'auto' }}>
        <table className="summary-table">
          <thead>
            <tr>
              <th>Business Line</th>
              <th>BL (%)</th>
              <th>Produkt</th>
              <th>Produkt (%)</th>
              <th>Aktivita</th>
              <th>Aktivita (%)</th>
              <th>Kanál</th>
              <th>Kanál (%)</th>
              <th>Alokácia (%)</th>
              <th>Weighted FTE</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i}>
                <td>{r.bl}</td>
                <td>{r.blPct}</td>
                <td>{r.product}</td>
                <td>{r.prodPct}</td>
                <td>{r.transType}</td>
                <td>{r.ttPct}</td>
                <td>{r.channel}</td>
                <td>{r.chPct}</td>
                <td>{r.allocPct}</td>
                <td>{r.weightedFte}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="metric-box" style={{ marginTop: 16 }}>
        <span className="metric-label">Celková finálna alokácia</span>
        <span className="metric-value">{fmtNum(finalTotal, 4)}%</span>
      </div>

      <div style={{ marginTop: 20 }}>
        <button className="btn-primary" onClick={handleDownload}>
          📥 Stiahnuť výsledky CSV
        </button>
      </div>
    </div>
  );
}
