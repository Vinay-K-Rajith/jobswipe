import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  IconAlertTriangle,
  IconArrowDownRight,
  IconArrowUpRight,
  IconBuildingSkyscraper,
  IconChartBar,
  IconFilterExclamation,
  IconRocket,
  IconScale,
  IconShieldCheck,
  IconSparkles,
} from '@tabler/icons-react';
import {
  BiasCompany,
  BiasReport,
  BiasSimulationResult,
  CounterfactualCandidate,
  CounterfactualRulesResult,
  FairnessHistoryResponse,
  MLFairnessComparison,
  SavedBiasRecommendation,
  SubstitutionPreviewResult,
  getBiasReport,
  getBiasRecommendations,
  getCounterfactualRules,
  getMLFairnessComparison,
  getModelFairnessHistory,
  previewSubstitution,
  retrainConstrainedModel,
  saveBiasRecommendation,
  simulateBiasFix,
} from '../services/api';
import { useAuthStore } from '../store/authStore';

type DetailTab = 'rules' | 'ml';

function formatPercent(value?: number | null, digits = 1) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatCriterionLabel(criterion?: string) {
  if (!criterion) return 'criterion';
  if (criterion === '10th' || criterion === 'tenth') return '10th marks';
  if (criterion === '12th' || criterion === 'twelfth') return '12th marks';
  if (criterion === 'cgpa') return 'CGPA';
  if (criterion === 'backlog') return 'active backlog cap';
  return criterion;
}

function metricTone(disparity?: number) {
  if (disparity === undefined) return 'neutral';
  if (disparity > 0.1) return 'danger';
  if (disparity > 0.05) return 'warning';
  return 'success';
}

function deltaClass(delta: number, preferLower: boolean) {
  if (preferLower) {
    return delta < 0 ? 'positive' : delta > 0 ? 'negative' : 'neutral';
  }
  return delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral';
}

function shortlistMembership(studentId: string, otherIds: Set<string>) {
  return otherIds.has(studentId) ? 'shared' : 'unique';
}

function formatSavedAt(value?: string) {
  if (!value) return '--';
  return new Date(value).toLocaleString();
}

export default function BiasDetection() {
  const [biasReport, setBiasReport] = useState<BiasReport | null>(null);
  const [pageError, setPageError] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [detailTab, setDetailTab] = useState<DetailTab>('rules');

  const [simulationByCompany, setSimulationByCompany] = useState<Record<string, BiasSimulationResult>>({});
  const [simulationLoading, setSimulationLoading] = useState<Record<string, boolean>>({});
  const [simulationError, setSimulationError] = useState<Record<string, string>>({});

  const [counterfactualByCompany, setCounterfactualByCompany] = useState<Record<string, CounterfactualRulesResult>>({});
  const [counterfactualLoading, setCounterfactualLoading] = useState<Record<string, boolean>>({});
  const [counterfactualError, setCounterfactualError] = useState<Record<string, string>>({});

  const [savingCompanyId, setSavingCompanyId] = useState<string>('');
  const [saveMessage, setSaveMessage] = useState<Record<string, string>>({});
  const [previewLoading, setPreviewLoading] = useState<Record<string, boolean>>({});
  const [previewError, setPreviewError] = useState<Record<string, string>>({});
  const [previewByCandidate, setPreviewByCandidate] = useState<Record<string, SubstitutionPreviewResult>>({});
  const [savedRecommendationsByCompany, setSavedRecommendationsByCompany] = useState<Record<string, SavedBiasRecommendation[]>>({});
  const [recommendationPersistenceByCompany, setRecommendationPersistenceByCompany] = useState<Record<string, 'supabase' | 'local'>>({});
  const [recommendationLoadError, setRecommendationLoadError] = useState<Record<string, string>>({});

  const [fairnessByCompany, setFairnessByCompany] = useState<Record<string, MLFairnessComparison>>({});
  const [fairnessLoading, setFairnessLoading] = useState<Record<string, boolean>>({});
  const [fairnessError, setFairnessError] = useState<Record<string, string>>({});

  const [fairnessHistoryByCompany, setFairnessHistoryByCompany] = useState<Record<string, FairnessHistoryResponse>>({});
  const [fairnessHistoryError, setFairnessHistoryError] = useState<Record<string, string>>({});

  const [epsilonDraft, setEpsilonDraft] = useState(0.01);
  const [committedEpsilon, setCommittedEpsilon] = useState<number | null>(null);
  const [retrainLoading, setRetrainLoading] = useState(false);
  const [retrainError, setRetrainError] = useState('');
  const [retrainMessage, setRetrainMessage] = useState('');

  const studentId = useAuthStore((state) => state.studentId);

  useEffect(() => {
    let cancelled = false;

    getBiasReport(false)
      .then((response) => {
        if (cancelled) return;
        setBiasReport(response.data);
        setSelectedCompanyId(
          response.data.flagged_companies[0]?.company_id ||
          response.data.all_companies?.[0]?.company_id ||
          '',
        );
        setPageError('');
      })
      .catch((error) => {
        if (cancelled) return;
        setPageError(error?.response?.data?.detail || 'Failed to load bias report.');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const sortedCompanies = useMemo(
    () => [...(biasReport?.all_companies || [])].sort((a, b) => b.gender_disparity - a.gender_disparity),
    [biasReport],
  );

  const selectedCompany = useMemo(
    () => sortedCompanies.find((company) => company.company_id === selectedCompanyId) || sortedCompanies[0],
    [selectedCompanyId, sortedCompanies],
  );

  const selectedFlag = biasReport?.flagged_companies.find((company) => company.company_id === selectedCompany?.company_id);
  const selectedSimulation = selectedCompany ? simulationByCompany[selectedCompany.company_id] : undefined;
  const selectedCounterfactual = selectedCompany ? counterfactualByCompany[selectedCompany.company_id] : undefined;
  const selectedFairness = selectedCompany ? fairnessByCompany[selectedCompany.company_id] : undefined;
  const selectedFairnessHistory = selectedCompany ? fairnessHistoryByCompany[selectedCompany.company_id] : undefined;

  const passRates = Object.entries(selectedCompany?.gender_pass_rates || selectedFlag?.pass_rates || {}).map(([group, rate]) => ({
    group,
    rate: Math.round((rate as number) * 1000) / 10,
  }));

  const baselineVariant = selectedFairness?.variants.find((variant) => variant.key === 'baseline' && variant.available);
  const championVariant = selectedFairness?.variants.find((variant) => variant.key === 'champion' && variant.available);
  const tightenedVariant = selectedFairness?.variants.find((variant) => variant.key === 'tightened' && variant.available);
  const shortlistA = baselineVariant?.shortlist || [];
  const shortlistB = championVariant?.shortlist || [];
  const shortlistBSet = new Set(shortlistB.map((student) => student.student_id));
  const shortlistASet = new Set(shortlistA.map((student) => student.student_id));
  const selectedSavedRecommendations = selectedCompany ? (savedRecommendationsByCompany[selectedCompany.company_id] || []) : [];
  const selectedRecommendationPersistence = selectedCompany ? recommendationPersistenceByCompany[selectedCompany.company_id] : undefined;

  const fairnessCallout = useMemo(() => {
    if (!baselineVariant?.available || !tightenedVariant?.available) {
      return null;
    }
    const accuracyTrade = ((baselineVariant.accuracy || 0) - (tightenedVariant.accuracy || 0)) * 100;
    const disparityReduction = ((baselineVariant.delta_dp || 0) - (tightenedVariant.delta_dp || 0)) * 100;
    return `At epsilon=${epsilonDraft.toFixed(3)}, the model trades ${accuracyTrade.toFixed(2)}% accuracy for ${disparityReduction.toFixed(2)}% reduction in gender disparity.`;
  }, [baselineVariant, tightenedVariant, epsilonDraft]);

  async function runSimulation(company: BiasCompany) {
    const companyId = company.company_id;
    setSelectedCompanyId(companyId);
    setSimulationLoading((current) => ({ ...current, [companyId]: true }));
    setSimulationError((current) => ({ ...current, [companyId]: '' }));
    setSaveMessage((current) => ({ ...current, [companyId]: '' }));

    try {
      const response = await simulateBiasFix(companyId, company.top_bias_criterion);
      setSimulationByCompany((current) => ({ ...current, [companyId]: response.data }));
      setSimulationError((current) => ({ ...current, [companyId]: '' }));

      setCounterfactualLoading((current) => ({ ...current, [companyId]: true }));
      setCounterfactualError((current) => ({ ...current, [companyId]: '' }));
      try {
        const counterfactualResponse = await getCounterfactualRules(companyId);
        setCounterfactualByCompany((current) => ({ ...current, [companyId]: counterfactualResponse.data }));
      } catch (error: any) {
        setCounterfactualError((current) => ({
          ...current,
          [companyId]: error?.response?.data?.detail || 'Failed to compute alternative rules.',
        }));
      } finally {
        setCounterfactualLoading((current) => ({ ...current, [companyId]: false }));
      }
    } catch (error: any) {
      setSimulationError((current) => ({
        ...current,
        [companyId]: error?.response?.data?.detail || 'Failed to simulate a rule fix.',
      }));
    } finally {
      setSimulationLoading((current) => ({ ...current, [companyId]: false }));
    }
  }

  async function handleSaveThresholdRecommendation() {
    if (!selectedCompany || !selectedSimulation || !selectedSimulation.recommended_result) {
      return;
    }

    setSavingCompanyId(selectedCompany.company_id);
    try {
      const response = await saveBiasRecommendation({
        company_id: selectedCompany.company_id,
        criterion: selectedSimulation.criterion,
        current_threshold: selectedSimulation.current_threshold,
        recommended_threshold: selectedSimulation.recommended_threshold,
        current_disparity: selectedSimulation.current_disparity,
        projected_disparity: selectedSimulation.recommended_result.gender_disparity,
        current_pool_size: selectedSimulation.current_pool_size,
        projected_pool_size: selectedSimulation.recommended_result.total_eligible,
        recommendation_type: 'threshold',
        simulation_payload: selectedSimulation,
      });
      setSavedRecommendationsByCompany((current) => ({
        ...current,
        [selectedCompany.company_id]: [response.data, ...(current[selectedCompany.company_id] || [])],
      }));
      setRecommendationPersistenceByCompany((current) => ({
        ...current,
        [selectedCompany.company_id]: response.data.persistence_mode,
      }));
      setSaveMessage((current) => ({
        ...current,
        [selectedCompany.company_id]: `Recommendation saved via ${response.data.persistence_mode}.`,
      }));
    } catch (error: any) {
      setSaveMessage((current) => ({
        ...current,
        [selectedCompany.company_id]: error?.response?.data?.detail || 'Failed to save recommendation.',
      }));
    } finally {
      setSavingCompanyId('');
    }
  }

  async function handlePreviewCandidate(candidate: CounterfactualCandidate) {
    if (!selectedCompany) return;

    setPreviewLoading((current) => ({ ...current, [candidate.candidate_id]: true }));
    setPreviewError((current) => ({ ...current, [candidate.candidate_id]: '' }));

    try {
      const response = await previewSubstitution(selectedCompany.company_id, candidate.spec);
      setPreviewByCandidate((current) => ({ ...current, [candidate.candidate_id]: response.data }));
    } catch (error: any) {
      setPreviewError((current) => ({
        ...current,
        [candidate.candidate_id]: error?.response?.data?.detail || 'Failed to preview substitution.',
      }));
    } finally {
      setPreviewLoading((current) => ({ ...current, [candidate.candidate_id]: false }));
    }
  }

  async function handleSaveSubstitution(candidate: CounterfactualCandidate) {
    if (!selectedCompany) return;

    setSavingCompanyId(candidate.candidate_id);
    try {
      const response = await saveBiasRecommendation({
        company_id: selectedCompany.company_id,
        criterion: candidate.current_rule.criterion,
        current_threshold: candidate.current_rule.threshold,
        recommended_threshold: candidate.alternative_rule.threshold,
        current_disparity: candidate.current_rule.gender_disparity,
        projected_disparity: candidate.alternative_rule.gender_disparity,
        current_pool_size: candidate.current_rule.pool_size,
        projected_pool_size: candidate.alternative_rule.pool_size,
        recommendation_type: 'substitution',
        simulation_payload: candidate,
      });
      setSavedRecommendationsByCompany((current) => ({
        ...current,
        [selectedCompany.company_id]: [response.data, ...(current[selectedCompany.company_id] || [])],
      }));
      setRecommendationPersistenceByCompany((current) => ({
        ...current,
        [selectedCompany.company_id]: response.data.persistence_mode,
      }));
      setSaveMessage((current) => ({
        ...current,
        [candidate.candidate_id]: `Substitution draft saved via ${response.data.persistence_mode}.`,
      }));
    } catch (error: any) {
      setSaveMessage((current) => ({
        ...current,
        [candidate.candidate_id]: error?.response?.data?.detail || 'Failed to save substitution draft.',
      }));
    } finally {
      setSavingCompanyId('');
    }
  }

  async function loadSavedRecommendations(companyId: string) {
    setRecommendationLoadError((current) => ({ ...current, [companyId]: '' }));
    try {
      const response = await getBiasRecommendations(companyId);
      setSavedRecommendationsByCompany((current) => ({ ...current, [companyId]: response.data.recommendations }));
      setRecommendationPersistenceByCompany((current) => ({ ...current, [companyId]: response.data.persistence_mode }));
    } catch (error: any) {
      setRecommendationLoadError((current) => ({
        ...current,
        [companyId]: error?.response?.data?.detail || 'Failed to load saved recommendations.',
      }));
    }
  }

  async function loadFairness(companyId: string) {
    setFairnessLoading((current) => ({ ...current, [companyId]: true }));
    setFairnessError((current) => ({ ...current, [companyId]: '' }));
    setFairnessHistoryError((current) => ({ ...current, [companyId]: '' }));

    try {
      const [comparisonResponse, historyResponse] = await Promise.all([
        getMLFairnessComparison(companyId),
        getModelFairnessHistory(companyId).catch((error) => {
          setFairnessHistoryError((current) => ({
            ...current,
            [companyId]: error?.response?.data?.detail || 'Failed to load fairness history.',
          }));
          return null;
        }),
      ]);

      setFairnessByCompany((current) => ({ ...current, [companyId]: comparisonResponse.data }));
      if (historyResponse) {
        setFairnessHistoryByCompany((current) => ({ ...current, [companyId]: historyResponse.data }));
      }
    } catch (error: any) {
      setFairnessError((current) => ({
        ...current,
        [companyId]: error?.response?.data?.detail || 'Failed to load ML fairness comparison.',
      }));
    } finally {
      setFairnessLoading((current) => ({ ...current, [companyId]: false }));
    }
  }

  useEffect(() => {
    if (!selectedCompany || detailTab !== 'ml' || fairnessByCompany[selectedCompany.company_id] || fairnessLoading[selectedCompany.company_id]) {
      return;
    }
    void loadFairness(selectedCompany.company_id);
  }, [detailTab, selectedCompany, fairnessByCompany, fairnessLoading]);

  useEffect(() => {
    if (!selectedCompany || savedRecommendationsByCompany[selectedCompany.company_id]) {
      return;
    }
    void loadSavedRecommendations(selectedCompany.company_id);
  }, [selectedCompany, savedRecommendationsByCompany]);

  useEffect(() => {
    if (!selectedCompany || detailTab !== 'ml' || committedEpsilon === null) {
      return;
    }

    const timer = window.setTimeout(async () => {
      setRetrainLoading(true);
      setRetrainError('');
      setRetrainMessage('');

      try {
        const response = await retrainConstrainedModel(
          selectedCompany.company_id,
          committedEpsilon,
          studentId || 'admin-dashboard',
        );
        setRetrainMessage(`Retrained constrained model in ${response.data.training_time_seconds.toFixed(2)}s.`);
        await loadFairness(selectedCompany.company_id);
      } catch (error: any) {
        setRetrainError(error?.response?.data?.detail || 'Failed to retrain constrained model.');
      } finally {
        setRetrainLoading(false);
      }
    }, 800);

    return () => window.clearTimeout(timer);
  }, [committedEpsilon, detailTab, selectedCompany, studentId]);

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Fairness audit</p>
          <h1>Bias Detection</h1>
          <p>Criteria-level disparate impact analysis with progressive bias reduction controls.</p>
        </div>
        {biasReport && (
          <div className="workspace-header-actions">
            <span>{biasReport.summary.student_pool_size} student pool</span>
            <span>p &lt; {biasReport.summary.significance}</span>
          </div>
        )}
      </header>

      {pageError ? (
        <section className="bento-card audit-empty">
          <h2>Bias report unavailable</h2>
          <p>{pageError}</p>
        </section>
      ) : !biasReport ? (
        <div className="loading"><div className="spinner"></div> Loading bias report...</div>
      ) : (
        <>
          <section className="audit-grid">
            <article className="audit-hero bento-card">
              <div className="bento-card-topline">
                <div>
                  <span className="bento-eyebrow"><IconScale size={15} /> Audit Summary</span>
                  <h2>{(biasReport.summary.flag_rate * 100).toFixed(1)}% gender flag rate</h2>
                </div>
                <span className="bento-pill">{biasReport.summary.n_companies} companies</span>
              </div>
              <p className="audit-finding">
                The current page still shows the original Fisher-based detection layer, but now the flagged company panel continues into a three-step reduction workflow: threshold tuning, rule substitution, and ML fairness inspection.
              </p>
              <div className="audit-stat-row">
                <div>
                  <strong>{biasReport.summary.n_flagged}</strong>
                  <span>flagged companies</span>
                </div>
                <div>
                  <strong>{(biasReport.summary.threshold * 100).toFixed(0)}%</strong>
                  <span>gap threshold</span>
                </div>
                <div>
                  <strong>Fisher</strong>
                  <span>significance test</span>
                </div>
              </div>
            </article>

            <article className="bento-card">
              <span className="bento-eyebrow"><IconFilterExclamation size={15} /> Risk Mix</span>
              <div className="risk-meter">
                <span style={{ width: `${Math.max(4, biasReport.summary.flag_rate * 100)}%` }} />
              </div>
              <div className="risk-meter-labels">
                <span>Clean: {biasReport.summary.n_companies - biasReport.summary.n_flagged}</span>
                <span>Flagged: {biasReport.summary.n_flagged}</span>
              </div>
            </article>

            <article className="bento-card">
              <span className="bento-eyebrow"><IconBuildingSkyscraper size={15} /> Gender Pool</span>
              <div className="pool-list">
                {Object.entries(biasReport.summary.gender_pool_dist).map(([gender, share]) => (
                  <div key={gender}>
                    <span>{gender}</span>
                    <strong>{((share as number) * 100).toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="audit-workspace">
            <aside className="bento-card audit-watchlist">
              <span className="bento-eyebrow"><IconAlertTriangle size={15} /> Flagged Watchlist</span>
              <div className="watchlist-stack">
                {biasReport.flagged_companies.map((company) => (
                  <div
                    className={`watchlist-item watchlist-item-panel ${selectedCompanyId === company.company_id ? 'active' : ''}`}
                    key={company.company_id}
                    onClick={() => setSelectedCompanyId(company.company_id)}
                  >
                    <span>
                      <strong>{company.company_name}</strong>
                      <small>{company.tier} - Driver: {formatCriterionLabel(company.top_bias_criterion)}</small>
                    </span>
                    <div className="watchlist-actions">
                      <b>{(company.disparity * 100).toFixed(1)}%</b>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          void runSimulation({
                            ...company,
                            pool_pass_rate: 0,
                            gender_disparity: company.disparity,
                            gender_p_value: company.p_value,
                            gender_flagged: true,
                            gender_pass_rates: company.pass_rates,
                            dept_disparity: 0,
                          });
                        }}
                      >
                        {simulationLoading[company.company_id] ? 'Running...' : 'Simulate fix'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </aside>

            <main className="bento-card audit-detail">
              <div className="bento-card-topline">
                <div>
                  <span className="bento-eyebrow"><IconChartBar size={15} /> Selected Company</span>
                  <h2>{selectedCompany?.company_name || 'No company selected'}</h2>
                </div>
                {selectedCompany && (
                  <span className={`bento-pill ${selectedCompany.gender_flagged ? 'danger' : 'success'}`}>
                    {selectedCompany.gender_flagged ? 'Flagged' : 'Clean'}
                  </span>
                )}
              </div>

              {selectedCompany && (
                <>
                  <div className="audit-detail-metrics">
                    <div>
                      <span>Pool pass rate</span>
                      <strong>{(selectedCompany.pool_pass_rate * 100).toFixed(1)}%</strong>
                    </div>
                    <div>
                      <span>Gender disparity</span>
                      <strong>{(selectedCompany.gender_disparity * 100).toFixed(1)}%</strong>
                    </div>
                    <div>
                      <span>p-value</span>
                      <strong>{selectedCompany.gender_p_value.toFixed(4)}</strong>
                    </div>
                    <div>
                      <span>Top driver</span>
                      <strong>{formatCriterionLabel(selectedCompany.top_bias_criterion)}</strong>
                    </div>
                  </div>

                  <div className="audit-chart-shell">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={passRates} margin={{ top: 10, right: 16, bottom: 0, left: -12 }}>
                        <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                        <XAxis dataKey="group" axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                        <Tooltip contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }} />
                        <Bar dataKey="rate" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="audit-tab-strip">
                    <button className={detailTab === 'rules' ? 'active' : ''} onClick={() => setDetailTab('rules')}>
                      Bias reduction pipeline
                    </button>
                    <button className={detailTab === 'ml' ? 'active' : ''} onClick={() => setDetailTab('ml')}>
                      ML fairness layer
                    </button>
                  </div>

                  {detailTab === 'rules' ? (
                    <section className="bias-reduction-stack">
                      <div className="bias-action-row">
                        <div>
                          <span className="bento-eyebrow"><IconRocket size={15} /> Level 1 - Criterion Sensitivity</span>
                          <p className="muted-text">
                            Sweep the flagged threshold for {formatCriterionLabel(selectedCompany.top_bias_criterion)} and measure the fairness-pool tradeoff before proposing a rule adjustment.
                          </p>
                        </div>
                        <button
                          className="btn btn-primary"
                          onClick={() => void runSimulation(selectedCompany)}
                          disabled={simulationLoading[selectedCompany.company_id]}
                        >
                          {simulationLoading[selectedCompany.company_id] ? 'Running simulation...' : `Simulate fix for ${formatCriterionLabel(selectedCompany.top_bias_criterion)}`}
                        </button>
                      </div>

                      {simulationError[selectedCompany.company_id] && (
                        <div className="bias-inline-error">{simulationError[selectedCompany.company_id]}</div>
                      )}

                      {!selectedSimulation ? (
                        <div className="bias-empty-panel">
                          <strong>No simulation yet</strong>
                          <span>Run Level 1 to unlock threshold optimization, substitution candidates, and company-ready recommendations.</span>
                        </div>
                      ) : (
                        <>
                          <div className="bias-simulation-card">
                            <div className="bias-simulation-chart">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={selectedSimulation.sweep} margin={{ top: 12, right: 16, left: -10, bottom: 8 }}>
                                  <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                                  <XAxis dataKey="threshold" axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                                  <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                                  <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                                  <Tooltip
                                    contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }}
                                    formatter={(value: any, name: string) => {
                                      if (name === 'gender_disparity') return [formatPercent(Number(value), 1), 'Gender disparity'];
                                      if (name === 'total_eligible') return [value, 'Eligible pool'];
                                      return [value, name];
                                    }}
                                    labelFormatter={(label) => `Threshold ${label}`}
                                  />
                                  <Legend />
                                  <ReferenceLine yAxisId="left" x={selectedSimulation.current_threshold} stroke="#a1a1aa" strokeDasharray="5 5" />
                                  {selectedSimulation.recommended_threshold !== null && (
                                    <ReferenceLine yAxisId="left" x={selectedSimulation.recommended_threshold} stroke="#14b8a6" strokeDasharray="5 5" />
                                  )}
                                  <Line yAxisId="left" type="monotone" dataKey="gender_disparity" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 3 }} name="Gender disparity" />
                                  <Line yAxisId="right" type="monotone" dataKey="total_eligible" stroke="#60a5fa" strokeWidth={2.5} dot={{ r: 3 }} name="Eligible pool" />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>

                            <div className="bias-simulation-summary">
                              <div className={`bias-recommendation-card ${selectedSimulation.recommended_result ? 'ready' : 'muted'}`}>
                                <strong>Recommendation</strong>
                                {selectedSimulation.recommended_result ? (
                                  <p>
                                    Lowering {formatCriterionLabel(selectedSimulation.criterion)} from {selectedSimulation.current_threshold} to {selectedSimulation.recommended_threshold}
                                    reduces gender disparity from {formatPercent(selectedSimulation.current_disparity)} to {formatPercent(selectedSimulation.recommended_result.gender_disparity)}
                                    while keeping {selectedSimulation.recommended_result.total_eligible} eligible students (
                                    {((selectedSimulation.recommended_result.total_eligible / Math.max(selectedSimulation.current_pool_size, 1)) * 100).toFixed(1)}% of the original pool).
                                  </p>
                                ) : (
                                  <p>No threshold in this sweep met the under-5%-gap and 80%-pool guardrails.</p>
                                )}
                                <div className="bias-action-row compact">
                                  <button
                                    className="btn btn-ghost"
                                    disabled={!selectedSimulation.recommended_result || savingCompanyId === selectedCompany.company_id}
                                    onClick={() => void handleSaveThresholdRecommendation()}
                                  >
                                    {savingCompanyId === selectedCompany.company_id ? 'Saving...' : 'Propose to company'}
                                  </button>
                                  {saveMessage[selectedCompany.company_id] && <span className="muted-text">{saveMessage[selectedCompany.company_id]}</span>}
                                </div>
                              </div>
                            </div>
                          </div>

                          <section className="bias-level-card">
                            <div className="bento-card-topline">
                              <div>
                                <span className="bento-eyebrow"><IconSparkles size={15} /> Level 2 - Counterfactual Rule Substitution</span>
                                <p className="muted-text">Find replacement rules that preserve pool size better than the original driver while lowering disparity.</p>
                              </div>
                              {counterfactualLoading[selectedCompany.company_id] && <span className="bento-pill">Finding alternatives...</span>}
                            </div>

                            {counterfactualError[selectedCompany.company_id] && (
                              <div className="bias-inline-error">{counterfactualError[selectedCompany.company_id]}</div>
                            )}

                            {!selectedCounterfactual ? (
                              <div className="bias-empty-panel slim">
                                <strong>Alternative rules will appear here</strong>
                                <span>Level 2 becomes available right after the sensitivity sweep completes.</span>
                              </div>
                            ) : (
                              <>
                                <div className="driver-strip">
                                  {selectedCounterfactual.drivers.map((driver) => (
                                    <div className="driver-pill" key={driver.criterion}>
                                      <strong>{formatCriterionLabel(driver.criterion)}</strong>
                                      <span>{formatPercent(driver.disparity_reduction)} disparity reduction if removed</span>
                                    </div>
                                  ))}
                                </div>

                                <div className="candidate-stack">
                                  {selectedCounterfactual.candidates.map((candidate) => {
                                    const disparityDelta = candidate.alternative_rule.gender_disparity - candidate.current_rule.gender_disparity;
                                    const poolDelta = candidate.alternative_rule.pool_size - candidate.current_rule.pool_size;
                                    const preview = previewByCandidate[candidate.candidate_id];
                                    return (
                                      <article className="candidate-card" key={candidate.candidate_id}>
                                        <div className="candidate-grid">
                                          <div className="candidate-column">
                                            <span className="candidate-label">Current rule</span>
                                            <strong>{formatCriterionLabel(candidate.current_rule.criterion)}</strong>
                                            <small>Threshold: {String(candidate.current_rule.threshold)}</small>
                                            <div className="candidate-metric-list">
                                              <span>Disparity {formatPercent(candidate.current_rule.gender_disparity)}</span>
                                              <span>Pool {candidate.current_rule.pool_size}</span>
                                            </div>
                                          </div>

                                          <div className="candidate-column">
                                            <span className="candidate-label">Alternative rule</span>
                                            <strong>{candidate.alternative_rule.label}</strong>
                                            <small>{candidate.description}</small>
                                            <div className="candidate-metric-list">
                                              <span className={`delta-chip ${deltaClass(disparityDelta, true)}`}>
                                                {disparityDelta < 0 ? <IconArrowDownRight size={14} /> : <IconArrowUpRight size={14} />}
                                                Disparity {formatPercent(candidate.alternative_rule.gender_disparity)}
                                              </span>
                                              <span className={`delta-chip ${deltaClass(poolDelta, false)} ${poolDelta < -(candidate.current_rule.pool_size * 0.15) ? 'warning' : ''}`}>
                                                {poolDelta >= 0 ? <IconArrowUpRight size={14} /> : <IconArrowDownRight size={14} />}
                                                Pool {candidate.alternative_rule.pool_size}
                                              </span>
                                              <span>Preservation {Math.round(candidate.alternative_rule.performance_preservation_score * 100)}%</span>
                                              <span className="confidence-chip">{candidate.confidence} confidence</span>
                                            </div>
                                          </div>
                                        </div>

                                        <div className="bias-action-row compact">
                                          <button
                                            className="btn btn-ghost"
                                            disabled={previewLoading[candidate.candidate_id]}
                                            onClick={() => void handlePreviewCandidate(candidate)}
                                          >
                                            {previewLoading[candidate.candidate_id] ? 'Previewing...' : 'Preview impact'}
                                          </button>
                                          <button
                                            className="btn btn-primary"
                                            disabled={savingCompanyId === candidate.candidate_id}
                                            onClick={() => void handleSaveSubstitution(candidate)}
                                          >
                                            {savingCompanyId === candidate.candidate_id ? 'Saving...' : 'Apply to simulation'}
                                          </button>
                                        </div>

                                        {saveMessage[candidate.candidate_id] && <p className="muted-text">{saveMessage[candidate.candidate_id]}</p>}
                                        {previewError[candidate.candidate_id] && <div className="bias-inline-error">{previewError[candidate.candidate_id]}</div>}

                                        {preview && (
                                          <div className="preview-panel">
                                            <div className="preview-summary">
                                              <div>
                                                <strong>{preview.newly_eligible_count}</strong>
                                                <span>newly eligible</span>
                                              </div>
                                              <div>
                                                <strong>{preview.dropped_count}</strong>
                                                <span>dropped</span>
                                              </div>
                                            </div>
                                            <div className="preview-groups">
                                              {preview.grouped.length === 0 ? (
                                                <span className="muted-text">No newly eligible students surfaced in this simulation.</span>
                                              ) : (
                                                preview.grouped.map((item) => (
                                                  <div key={`${candidate.candidate_id}-${item.department}-${item.gender}`}>
                                                    <strong>{item.department}</strong>
                                                    <span>{item.gender}: {item.count}</span>
                                                  </div>
                                                ))
                                              )}
                                            </div>
                                          </div>
                                        )}
                                      </article>
                                    );
                                  })}
                                </div>

                                <p className="muted-text">
                                  This is a simulation. Actual company criteria changes require company approval.
                                </p>
                              </>
                            )}
                          </section>

                          <section className="bias-level-card">
                            <div className="bento-card-topline">
                              <div>
                                <span className="bento-eyebrow"><IconBuildingSkyscraper size={15} /> Saved Recommendations</span>
                                <p className="muted-text">Review the proposals stored for this company and confirm whether they landed in Supabase or local fallback storage.</p>
                              </div>
                              {selectedRecommendationPersistence && (
                                <span className="bento-pill">Persistence: {selectedRecommendationPersistence}</span>
                              )}
                            </div>

                            {recommendationLoadError[selectedCompany.company_id] && (
                              <div className="bias-inline-error">{recommendationLoadError[selectedCompany.company_id]}</div>
                            )}

                            {!selectedSavedRecommendations.length ? (
                              <div className="bias-empty-panel slim">
                                <strong>No saved recommendations yet</strong>
                                <span>Once you save a threshold or substitution proposal, it will appear here with its actual storage mode.</span>
                              </div>
                            ) : (
                              <div className="candidate-stack">
                                {selectedSavedRecommendations.slice(0, 6).map((item) => (
                                  <article className="candidate-card" key={item.id}>
                                    <div className="candidate-grid">
                                      <div className="candidate-column">
                                        <span className="candidate-label">{item.recommendation_type}</span>
                                        <strong>{formatCriterionLabel(item.criterion)}</strong>
                                        <small>Saved {formatSavedAt(item.created_at)}</small>
                                      </div>
                                      <div className="candidate-column">
                                        <span className="candidate-label">Change</span>
                                        <strong>{String(item.current_threshold ?? '--')} to {String(item.recommended_threshold ?? '--')}</strong>
                                        <small>
                                          Disparity {formatPercent(item.current_disparity)} to {formatPercent(item.projected_disparity)} and pool {item.current_pool_size ?? '--'} to {item.projected_pool_size ?? '--'}
                                        </small>
                                      </div>
                                    </div>
                                    <p className="muted-text">Stored via {item.persistence_mode} with status {item.status}.</p>
                                  </article>
                                ))}
                              </div>
                            )}
                          </section>
                        </>
                      )}
                    </section>
                  ) : (
                    <section className="bias-reduction-stack">
                      <div className="bento-card-topline">
                        <div>
                          <span className="bento-eyebrow"><IconShieldCheck size={15} /> Level 3 - ML Fairness Layer</span>
                          <p className="muted-text">Compare the baseline ranking model against constrained variants and make the accuracy-fairness tradeoff visible.</p>
                        </div>
                        {fairnessLoading[selectedCompany.company_id] && <span className="bento-pill">Loading comparison...</span>}
                      </div>

                      {fairnessError[selectedCompany.company_id] && (
                        <div className="bias-inline-error">{fairnessError[selectedCompany.company_id]}</div>
                      )}

                      {!selectedFairness ? (
                        <div className="bias-empty-panel">
                          <strong>ML fairness comparison not loaded</strong>
                          <span>Open this tab on a flagged company to fetch the persisted model comparison.</span>
                        </div>
                      ) : (
                        <>
                          <div className="fairness-table-card">
                            <table className="fairness-table">
                              <thead>
                                <tr>
                                  <th>Metric</th>
                                  {selectedFairness.variants.map((variant) => (
                                    <th key={variant.key}>{variant.label}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td>Availability</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-available`} className={variant.available ? 'tone-success' : 'tone-warning'}>
                                      {variant.available
                                        ? (variant.artifact_path ? `Ready (${variant.artifact_path})` : 'Ready')
                                        : variant.detail || 'Missing artifact'}
                                    </td>
                                  ))}
                                </tr>
                                <tr>
                                  <td>Accuracy</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-accuracy`} className="metric-cell">{variant.available ? formatPercent(variant.accuracy, 2) : '--'}</td>
                                  ))}
                                </tr>
                                <tr>
                                  <td>F1</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-f1`} className="metric-cell">{variant.available && variant.f1 !== undefined ? variant.f1.toFixed(4) : '--'}</td>
                                  ))}
                                </tr>
                                <tr>
                                  <td>Delta DP</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-dp`} className={`metric-cell tone-${metricTone(variant.delta_dp)}`}>
                                      {variant.available ? formatPercent(variant.delta_dp, 2) : '--'}
                                    </td>
                                  ))}
                                </tr>
                                <tr>
                                  <td>Delta EO</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-eo`} className="metric-cell">{variant.available ? formatPercent(variant.delta_eo, 2) : '--'}</td>
                                  ))}
                                </tr>
                                <tr>
                                  <td>Shortlist overlap</td>
                                  {selectedFairness.variants.map((variant) => (
                                    <td key={`${variant.key}-overlap`} className="metric-cell">{variant.available ? formatPercent(variant.shortlist_overlap, 2) : '--'}</td>
                                  ))}
                                </tr>
                              </tbody>
                            </table>
                          </div>

                          <div className="shortlist-diff-grid">
                            <article className="shortlist-card">
                              <span className="bento-eyebrow">Variant A shortlist</span>
                              <div className="shortlist-list">
                                {shortlistA.slice(0, 10).map((student, index) => (
                                  <div className={`shortlist-row ${shortlistMembership(student.student_id, shortlistBSet)}`} key={`a-${student.student_id}`}>
                                    <strong>{index + 1}</strong>
                                    <span>{student.full_name}</span>
                                  </div>
                                ))}
                              </div>
                            </article>
                            <article className="shortlist-card">
                              <span className="bento-eyebrow">Variant B shortlist</span>
                              <div className="shortlist-list">
                                {shortlistB.slice(0, 10).map((student, index) => (
                                  <div className={`shortlist-row ${shortlistMembership(student.student_id, shortlistASet)}`} key={`b-${student.student_id}`}>
                                    <strong>{index + 1}</strong>
                                    <span>{student.full_name}</span>
                                  </div>
                                ))}
                              </div>
                            </article>
                          </div>

                          <section className="epsilon-panel">
                            <div className="epsilon-header">
                              <div>
                                <span className="bento-eyebrow">Live retraining</span>
                                <p className="muted-text">Tighten demographic parity tolerance and inspect the tradeoff on release.</p>
                              </div>
                              <strong>epsilon {epsilonDraft.toFixed(3)}</strong>
                            </div>
                            <input
                              type="range"
                              min={0.001}
                              max={0.05}
                              step={0.001}
                              value={epsilonDraft}
                              onChange={(event) => setEpsilonDraft(Number(event.target.value))}
                              onMouseUp={() => setCommittedEpsilon(epsilonDraft)}
                              onTouchEnd={() => setCommittedEpsilon(epsilonDraft)}
                            />
                            <p className="muted-text">
                              {fairnessCallout || 'Constrained model artifacts are not available yet for a live comparison in this environment.'}
                            </p>
                            {retrainLoading && <span className="bento-pill">Retraining...</span>}
                            {retrainError && <div className="bias-inline-error">{retrainError}</div>}
                            {retrainMessage && <p className="muted-text">{retrainMessage}</p>}
                          </section>

                          <section className="history-panel">
                            <div className="bento-card-topline">
                              <span className="bento-eyebrow">Fairness history</span>
                              {selectedFairnessHistory?.history?.length ? (
                                <span className="bento-pill">{selectedFairnessHistory.history.length} runs</span>
                              ) : null}
                            </div>
                            {fairnessHistoryError[selectedCompany.company_id] ? (
                              <div className="bias-inline-error">{fairnessHistoryError[selectedCompany.company_id]}</div>
                            ) : !selectedFairnessHistory?.history?.length ? (
                              <div className="bias-empty-panel slim">
                                <strong>No fairness retrain history yet</strong>
                                <span>Saved retraining runs will appear here once Supabase persistence is available.</span>
                              </div>
                            ) : (
                              <div className="history-chart-shell">
                                <ResponsiveContainer width="100%" height="100%">
                                  <LineChart data={selectedFairnessHistory.history}>
                                    <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                                    <XAxis dataKey="trained_at" hide />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                                    <Tooltip
                                      contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }}
                                      formatter={(value: any, name: string) => [name === 'delta_dp' ? formatPercent(Number(value), 2) : value, name]}
                                    />
                                    <Line type="monotone" dataKey="delta_dp" stroke="#14b8a6" strokeWidth={2.5} dot={{ r: 3 }} />
                                  </LineChart>
                                </ResponsiveContainer>
                              </div>
                            )}
                          </section>
                        </>
                      )}
                    </section>
                  )}
                </>
              )}
            </main>
          </section>

          <section className="bento-card audit-table-card">
            <div className="bento-card-topline">
              <span className="bento-eyebrow"><IconShieldCheck size={15} /> Full Company Ranking</span>
              <span className="bento-pill">sorted by disparity</span>
            </div>
            <div className="table-container workspace-table">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Tier</th>
                    <th>Pool Pass</th>
                    <th>Disparity</th>
                    <th>p-value</th>
                    <th>Driver</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCompanies.map((company: BiasCompany) => (
                    <tr key={company.company_id}>
                      <td><strong>{company.company_name}</strong></td>
                      <td><span className="badge badge-info">{company.tier}</span></td>
                      <td>{(company.pool_pass_rate * 100).toFixed(1)}%</td>
                      <td>{(company.gender_disparity * 100).toFixed(1)}%</td>
                      <td>{company.gender_p_value.toFixed(4)}</td>
                      <td>{formatCriterionLabel(company.top_bias_criterion)}</td>
                      <td>
                        <span className={`badge ${company.gender_flagged ? 'badge-warning' : 'badge-success'}`}>
                          {company.gender_flagged ? 'Review' : 'Clean'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
