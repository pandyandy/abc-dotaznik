import { useState, useEffect, useCallback } from 'react';
import {
  buildHierarchy,
  getFormStatus,
  getMaxStatus,
  statusLevel,
  loadSelectionsFromRows,
} from './utils/hierarchy';
import StepUserInput from './components/StepUserInput';
import StepBL from './components/StepBL';
import StepProducts from './components/StepProducts';
import StepActivities from './components/StepActivities';
import StepChannels from './components/StepChannels';
import StepSummary from './components/StepSummary';
import StepBSForm from './components/StepBSForm';
import StepBSSummary from './components/StepBSSummary';

const ABC_STEPS  = ['step1', 'step2', 'step3', 'step4', 'summary'];
const ABC_LABELS = ['Biznis línie', 'Produkty', 'Aktivity', 'Kanály', 'Zhrnutie'];
const BS_STEPS   = ['bs_step1', 'bs_summary'];
const BS_LABELS  = ['Alokácia', 'Zhrnutie'];

function StepProgress({ currentStep, steps, labels }) {
  const currentIdx = steps.indexOf(currentStep);
  const items = [];
  steps.forEach((step, i) => {
    if (i > 0) {
      items.push(
        <div key={`conn-${step}`} className={`step-progress-connector${i <= currentIdx ? ' done' : ''}`} />
      );
    }
    items.push(
      <div key={step} className={`step-progress-item${i < currentIdx ? ' done' : i === currentIdx ? ' active' : ''}`}>
        <div className="step-progress-num">{i < currentIdx ? '✓' : i + 1}</div>
        <div className="step-progress-label">{labels[i]}</div>
      </div>
    );
  });
  return <div className="step-progress">{items}</div>;
}

const INIT = {
  step: 'user_input',
  userId: null,
  cc: null,
  ccDesc: '',
  formType: null,
  currentStatusSnapshot: '',
  selectedBls: {},
  selectedProducts: {},
  selectedTransTypes: {},
  selectedChannels: {},
};

export default function App() {
  const [staticData, setStaticData] = useState(null);
  const [dynamicData, setDynamicData] = useState(null);
  const [hierarchy, setHierarchy] = useState(null);
  const [state, setState] = useState(INIT);
  const [loading, setLoading] = useState(true);
  const [loadElapsedSec, setLoadElapsedSec] = useState(0);
  const [saveStatus, setSaveStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
  const [error, setError] = useState(null);

  // ── Load everything in one request (server runs all Storage exports in parallel) ──
  useEffect(() => {
    let cancelled = false;
    const t0 = Date.now();
    const tickId = setInterval(() => {
      if (!cancelled) setLoadElapsedSec(Math.floor((Date.now() - t0) / 1000));
    }, 1000);

    (async () => {
      try {
        console.info('[app] GET /api/data (proxied to port 3000 in dev) …');
        const res = await fetch('/api/data');
        const text = await res.text();
        if (!res.ok) {
          throw new Error(
            `HTTP ${res.status}: ${text.slice(0, 280) || res.statusText}`
          );
        }
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          throw new Error(
            'API nevrátila JSON. Beží backend? Spustite `npm run dev:all` alebo v druhom termináli `npm start`.'
          );
        }
        if (data.error) throw new Error(data.error);
        const { ccUser, savedForms, savedBs, ...staticPart } = data;
        if (!cancelled) {
          setStaticData(staticPart);
          setDynamicData({ ccUser, savedForms, savedBs });
          setHierarchy(buildHierarchy(data.transData));
        }
      } catch (e) {
        let msg = e.message || String(e);
        if (
          msg === 'Failed to fetch' ||
          /network/i.test(msg) ||
          /load failed/i.test(msg)
        ) {
          msg +=
            ' Spustite API a UI spolu: `npm run dev:all`, alebo `npm start` (port 3000) a v druhom okne `npm run dev`.';
        }
        if (!cancelled) setError(msg);
      } finally {
        clearInterval(tickId);
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      clearInterval(tickId);
    };
  }, []);

  const refreshDynamic = useCallback(async () => {
    if (!staticData?.actVersion) {
      const empty = { ccUser: [], savedForms: [], savedBs: [] };
      setDynamicData(empty);
      return empty;
    }
    const q = new URLSearchParams({
      actVersion: staticData.actVersion,
      prevVersion: staticData.prevVersion ?? '',
    });
    const res = await fetch(`/api/dynamic-data?${q}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setDynamicData(data);
    return data;
  }, [staticData]);

  // ── Dynamic data is included in /api/data; refreshDynamic() is for user actions only ──

  // ── Step: user_input → continue ───────────────────────────────────────────
  const handleUserInputNext = useCallback(
    async (userId, cc) => {
      try {
        // Initial /api/data already loaded cc_user + saved_* — no need to hit Keboola again.
        let dyn = dynamicData;
        const haveDyn =
          dyn &&
          Array.isArray(dyn.savedForms) &&
          Array.isArray(dyn.savedBs) &&
          Array.isArray(dyn.ccUser);
        if (!haveDyn) {
          setLoading(true);
          dyn = await refreshDynamic();
        }
        const { savedForms, savedBs, ccUser } = dyn;
        const { actVersion, prevVersion, prodMaskOrder, channelMaskOrder } = staticData;

        const currentStatus = getMaxStatus(savedForms, cc, actVersion);
        const formStatus = getFormStatus(savedForms, cc, actVersion);

        // Determine which rows to pre-load
        let existingRows;
        if (!formStatus) {
          existingRows = prevVersion
            ? savedForms.filter(
                (r) =>
                  String(r.CC || '').trim() === String(cc).trim() &&
                  String(r.VERSION || '').trim() === String(prevVersion).trim()
              )
            : [];
        } else {
          existingRows = savedForms.filter(
            (r) =>
              String(r.CC || '').trim() === String(cc).trim() &&
              String(r.VERSION || '').trim() === String(actVersion).trim() &&
              String(r.STATUS || '') === formStatus
          );
        }

        const selections = loadSelectionsFromRows(existingRows, prodMaskOrder, channelMaskOrder);

        // Determine form type from cc_user
        const ccUserRow = ccUser.find((r) => String(r.CC || '').trim() === String(cc).trim());
        const formType = (ccUserRow?.FORM_TYPE || 'ABC').trim();

        // Get CC description
        const ccDescRow = staticData.ccDesc.find(
          (r) => String(r.ID || '').trim() === String(cc).trim()
        );
        const ccDescText = ccDescRow?.TXT_DESCRIPTION || '';

        setState((s) => ({
          ...s,
          userId,
          cc,
          ccDesc: ccDescText,
          formType,
          currentStatusSnapshot: currentStatus,
          ...selections,
          step: formType === 'BS' ? 'bs_step1' : 'step1',
        }));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [staticData, dynamicData, refreshDynamic]
  );

  // ── Generic save helper (fire-and-forget — navigation does not wait for Keboola write) ──
  const saveForm = useCallback(
    (rows, status) => {
      setSaveStatus('saving');
      fetch('/api/save-form', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: state.userId,
          cc: state.cc,
          actVersion: staticData.actVersion,
          status,
          rows,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.error) throw new Error(data.error);
          if (data.savedForms)
            setDynamicData((d) => (d ? { ...d, savedForms: data.savedForms } : d));
          else refreshDynamic();
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus((s) => (s === 'saved' ? null : s)), 3000);
        })
        .catch(() => setSaveStatus('error'));
    },
    [state.userId, state.cc, staticData, refreshDynamic]
  );

  const saveBs = useCallback(
    (allocations) => {
      setSaveStatus('saving');
      fetch('/api/save-bs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: state.userId,
          cc: state.cc,
          actVersion: staticData.actVersion,
          allocations,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.error) throw new Error(data.error);
          if (data.savedBs)
            setDynamicData((d) => (d ? { ...d, savedBs: data.savedBs } : d));
          else refreshDynamic();
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus((s) => (s === 'saved' ? null : s)), 3000);
        })
        .catch(() => setSaveStatus('error'));
    },
    [state.userId, state.cc, staticData, refreshDynamic]
  );

  // ── Navigation helpers ─────────────────────────────────────────────────────
  const goTo = (step, extra = {}) =>
    setState((s) => ({ ...s, step, ...extra }));

  const resetToUserInput = () => setState(INIT);

  // ── Render ─────────────────────────────────────────────────────────────────
  const header = (
    <header className="app-header">
      <div className="app-header-inner">
        <img src="/slsp.png" className="app-logo" alt="Slovenská sporiteľňa" />
        <span className="app-header-label">ABC dotazník</span>
      </div>
    </header>
  );

  if (error) {
    return (
      <div className="page-root">
        {header}
        <div className="app-wrapper">
          <div className="msg msg-error">
            <strong>Chyba:</strong> {error}
            <br />
            <button className="btn-secondary" style={{ marginTop: 10 }} onClick={() => setError(null)}>
              Skúsiť znova
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading || !staticData) {
    const bootstrapping = !staticData;
    return (
      <div className="page-root">
        {header}
        <div className="loading-page">
          <div className="spinner" />
          {bootstrapping ? (
            <>
              <span>Načítavam dáta z Keboola… ({loadElapsedSec}s)</span>
              <p className="loading-hint">
                Prvé načítanie volá Storage API (12 tabuliek naraz) — môže trvať desiatky sekúnd.
                Logy s časovaním tabuliek uvidíte v termináli, kde beží <code>npm start</code> /{' '}
                <code>npm run dev:all</code>.
              </p>
            </>
          ) : (
            <span>Obnovujem dáta…</span>
          )}
        </div>
      </div>
    );
  }

  const sharedProps = {
    staticData,
    dynamicData,
    state,
    onResetToUserInput: resetToUserInput,
  };

  return (
    <div className="page-root">
      {header}

      {saveStatus && (
        <div className={`save-toast save-toast-${saveStatus}`}>
          {saveStatus === 'saving' && 'Ukladám...'}
          {saveStatus === 'saved' && '✓ Uložené'}
          {saveStatus === 'error' && '✗ Chyba pri ukladaní'}
        </div>
      )}

      <div className="app-wrapper">

      {/* DEBUG strip – remove before go-live */}
      <div className="debug-strip">
        🔍 DEBUG — Version: <strong>{staticData.actVersion}</strong>
        {staticData.prevVersion ? ` | Prev: ${staticData.prevVersion}` : ''}
        {state.cc ? ` | CC: ${state.cc}` : ''}
        {state.currentStatusSnapshot ? ` | Status: ${state.currentStatusSnapshot}` : ''}
      </div>

      {ABC_STEPS.includes(state.step) && (
        <StepProgress currentStep={state.step} steps={ABC_STEPS} labels={ABC_LABELS} />
      )}
      {BS_STEPS.includes(state.step) && (
        <StepProgress currentStep={state.step} steps={BS_STEPS} labels={BS_LABELS} />
      )}

      {state.step === 'user_input' && (
        <StepUserInput
          {...sharedProps}
          onNext={handleUserInputNext}
        />
      )}

      {state.step === 'step1' && (
        <StepBL
          {...sharedProps}
          hierarchy={hierarchy}
          onBack={() => goTo('user_input')}
          onNext={(selectedBls) => {
            setState((s) => ({ ...s, selectedBls, step: 'step2' }));
          }}
          onSave={saveForm}
        />
      )}

      {state.step === 'step2' && (
        <StepProducts
          {...sharedProps}
          hierarchy={hierarchy}
          onBack={() => goTo('step1')}
          onNext={(selectedProducts) => {
            setState((s) => ({ ...s, selectedProducts, step: 'step3' }));
          }}
          onSave={saveForm}
        />
      )}

      {state.step === 'step3' && (
        <StepActivities
          {...sharedProps}
          hierarchy={hierarchy}
          onBack={() => goTo('step2')}
          onNext={(selectedTransTypes) => {
            setState((s) => ({ ...s, selectedTransTypes, step: 'step4' }));
          }}
          onSave={saveForm}
        />
      )}

      {state.step === 'step4' && (
        <StepChannels
          {...sharedProps}
          hierarchy={hierarchy}
          onBack={() => goTo('step3')}
          onNext={(selectedChannels) => {
            setState((s) => ({ ...s, selectedChannels, step: 'summary' }));
          }}
          onSave={saveForm}
        />
      )}

      {state.step === 'summary' && (
        <StepSummary
          {...sharedProps}
          onBack={() => goTo('step4')}
        />
      )}

      {state.step === 'bs_step1' && (
        <StepBSForm
          {...sharedProps}
          hierarchy={hierarchy}
          onBack={resetToUserInput}
          onNext={(selectedBls) => {
            setState((s) => ({ ...s, selectedBls, step: 'bs_summary' }));
          }}
          onSave={saveBs}
        />
      )}

      {state.step === 'bs_summary' && (
        <StepBSSummary
          {...sharedProps}
          onBack={() => goTo('bs_step1')}
        />
      )}

      </div>
    </div>
  );
}
