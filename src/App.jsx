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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // ── Load static data once ──────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/static-data')
      .then((r) => r.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setStaticData(data);
        setHierarchy(buildHierarchy(data.transData));
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  const refreshDynamic = useCallback(async () => {
    const res = await fetch('/api/dynamic-data');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setDynamicData(data);
    return data;
  }, []);

  // ── Load dynamic data on mount ─────────────────────────────────────────────
  useEffect(() => {
    if (!staticData) return;
    refreshDynamic().catch((e) => setError(e.message));
  }, [staticData, refreshDynamic]);

  // ── Step: user_input → continue ───────────────────────────────────────────
  const handleUserInputNext = useCallback(
    async (userId, cc) => {
      setLoading(true);
      try {
        const dyn = await refreshDynamic();
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
    [staticData, refreshDynamic]
  );

  // ── Generic save helper ────────────────────────────────────────────────────
  const saveForm = useCallback(
    async (rows, status) => {
      setSaving(true);
      try {
        const res = await fetch('/api/save-form', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            userId: state.userId,
            cc: state.cc,
            actVersion: staticData.actVersion,
            status,
            rows,
          }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        await refreshDynamic();
      } finally {
        setSaving(false);
      }
    },
    [state.userId, state.cc, staticData, refreshDynamic]
  );

  const saveBs = useCallback(
    async (allocations) => {
      setSaving(true);
      try {
        const res = await fetch('/api/save-bs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            userId: state.userId,
            cc: state.cc,
            actVersion: staticData.actVersion,
            allocations,
          }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        await refreshDynamic();
      } finally {
        setSaving(false);
      }
    },
    [state.userId, state.cc, staticData, refreshDynamic]
  );

  // ── Navigation helpers ─────────────────────────────────────────────────────
  const goTo = (step, extra = {}) =>
    setState((s) => ({ ...s, step, ...extra }));

  const resetToUserInput = () => setState(INIT);

  // ── Render ─────────────────────────────────────────────────────────────────
  const title = state.ccDesc
    ? `ABC dotazník – ${state.ccDesc}`
    : 'ABC dotazník';

  if (error) {
    return (
      <div className="app-wrapper">
        <div className="msg msg-error">
          <strong>Chyba:</strong> {error}
          <br />
          <button className="btn-secondary" style={{ marginTop: 10 }} onClick={() => setError(null)}>
            Skúsiť znova
          </button>
        </div>
      </div>
    );
  }

  if (loading || !staticData) {
    return (
      <div className="app-wrapper">
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Načítavam dáta z Keboola…</span>
        </div>
      </div>
    );
  }

  const sharedProps = {
    staticData,
    dynamicData,
    state,
    saving,
    onResetToUserInput: resetToUserInput,
  };

  return (
    <div className="app-wrapper">
      <div className="app-header">
        <h1>📊 {title}</h1>
      </div>

      {/* DEBUG strip – remove before go-live */}
      <div className="debug-strip">
        🔍 DEBUG — Version: <strong>{staticData.actVersion}</strong>
        {staticData.prevVersion ? ` | Prev: ${staticData.prevVersion}` : ''}
        {state.cc ? ` | CC: ${state.cc}` : ''}
        {state.currentStatusSnapshot ? ` | Status: ${state.currentStatusSnapshot}` : ''}
      </div>

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
  );
}
