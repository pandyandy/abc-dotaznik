import { useState } from 'react';

export default function StepUserInput({ staticData, dynamicData, onNext }) {
  const [userId, setUserId] = useState('');
  const [cc, setCc] = useState('');
  const [validationMsg, setValidationMsg] = useState('');

  const userIdValid = /^4\d{5}$/.test(userId.trim());

  const allowedCcs = userIdValid && dynamicData
    ? [...new Set(
        dynamicData.ccUser
          .filter((r) => String(r.USER_ID || '').trim() === userId.trim())
          .map((r) => String(r.CC || '').trim())
      )].sort()
    : [];

  const ccOptions = allowedCcs.map((c) => {
    const descRow = staticData.ccDesc.find((r) => String(r.ID || '').trim() === c);
    const desc = descRow?.TXT_DESCRIPTION || '';
    return { value: c, label: desc ? `${c} - ${desc}` : c };
  });

  const handleUserIdChange = (e) => {
    setUserId(e.target.value);
    setValidationMsg('');
    setCc('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!userIdValid) {
      setValidationMsg('User ID musí začínať číslom 4 a byť presne 6 miestne.');
      return;
    }
    if (allowedCcs.length === 0) {
      setValidationMsg('User ID nie je v zozname editorov ABC kľúčov.');
      return;
    }
    const selectedCc = cc || allowedCcs[0];
    onNext(userId.trim(), selectedCc);
  };

  return (
    <div className="card">
      <h2>Zadajte vaše údaje</h2>
      <p className="card-desc">
        Pred začatím vyplnenia formulára zadajte svoje osobné číslo a nákladové stredisko.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>User ID</label>
          <input
            type="text"
            value={userId}
            onChange={handleUserIdChange}
            placeholder="4XXXXX"
            maxLength={6}
          />
          {userId && !userIdValid && (
            <div className="msg msg-warning" style={{ marginTop: 6 }}>
              User ID musí začínať číslom 4 a byť presne 6 miestne.
            </div>
          )}
          {userIdValid && allowedCcs.length === 0 && dynamicData && (
            <div className="msg msg-error" style={{ marginTop: 6 }}>
              User ID nie je v zozname editorov ABC kľúčov.
            </div>
          )}
          {userIdValid && allowedCcs.length > 0 && (
            <div className="msg msg-success" style={{ marginTop: 6 }}>
              User ID {userId} je platné.
            </div>
          )}
        </div>

        {allowedCcs.length > 0 && (
          <div className="form-group">
            <label>Nákladové stredisko</label>
            <select
              value={cc || allowedCcs[0]}
              onChange={(e) => setCc(e.target.value)}
            >
              {ccOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        )}

        {validationMsg && (
          <div className="msg msg-error">{validationMsg}</div>
        )}

        <button
          type="submit"
          className="btn-primary"
          disabled={!userIdValid || allowedCcs.length === 0 || !dynamicData}
        >
          Pokračovať →
        </button>
      </form>
    </div>
  );
}
