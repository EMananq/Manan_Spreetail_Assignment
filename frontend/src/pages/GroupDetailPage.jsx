import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getGroup, getExpenses, getBalances, getSettlements,
  getMembers, getUsers, createExpense, createSettlement, importCSV,
  getImportReports, reviewAnomaly, addMember, updateMembership,
} from '../api';

/* ═══════════════════════════════════════════════════════
   UTILITY HELPERS
   ═══════════════════════════════════════════════════════ */

function getAvatarClass(name) {
  const classes = ['avatar-a', 'avatar-b', 'avatar-c', 'avatar-d', 'avatar-e', 'avatar-f'];
  return classes[(name || '').charCodeAt(0) % classes.length];
}

function formatCurrency(amount, currency = 'INR') {
  const num = parseFloat(amount);
  if (isNaN(num)) return '₹0.00';
  const symbol = currency === 'USD' ? '$' : '₹';
  return `${symbol}${Math.abs(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  } catch { return dateStr; }
}

/* ═══════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════ */

export default function GroupDetailPage() {
  const { groupId } = useParams();
  const [group, setGroup] = useState(null);
  const [tab, setTab] = useState('balances');
  const [loading, setLoading] = useState(true);

  // Data
  const [expenses, setExpenses] = useState([]);
  const [balances, setBalances] = useState(null);
  const [settlements, setSettlements] = useState([]);
  const [members, setMembers] = useState([]);
  const [importReports, setImportReports] = useState([]);

  // Import state
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const [missingPayerAssignments, setMissingPayerAssignments] = useState({});

  // Modals
  const [showExpenseModal, setShowExpenseModal] = useState(false);
  const [showSettleModal, setShowSettleModal] = useState(false);
  const [showMemberModal, setShowMemberModal] = useState(false);
  const [settlePreFill, setSettlePreFill] = useState(null);

  // Expense drill-down
  const [drillUser, setDrillUser] = useState(null);
  
  // Expense detail expand
  const [expandedExpense, setExpandedExpense] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [g, e, b, s, m, r] = await Promise.all([
        getGroup(groupId),
        getExpenses(groupId),
        getBalances(groupId),
        getSettlements(groupId),
        getMembers(groupId),
        getImportReports(groupId),
      ]);
      setGroup(g.data);
      setExpenses(e.data);
      setBalances(b.data);
      setSettlements(s.data);
      setMembers(m.data);
      setImportReports(r.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }, [groupId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ── CSV Import ──────────────────────────────────────────
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      setImporting(true);
      try {
        const res = await importCSV(groupId, ev.target.result, 'preview');
        setImportResult(res.data);
      } catch (err) {
        console.error(err);
        alert('Import failed: ' + (err.response?.data?.error || err.message));
      }
      setImporting(false);
    };
    reader.readAsText(file);
  };

  const handleImportConfirm = async () => {
    setImporting(true);
    try {
      const csvInput = document.getElementById('csv-input');
      const file = csvInput?.files?.[0];
      if (!file) { alert('Please select the CSV file again'); setImporting(false); return; }
      const text = await file.text();
      const res = await importCSV(groupId, text, 'import', missingPayerAssignments);
      setImportResult(res.data);
      fetchAll();
      alert(`Import complete! ${res.data.summary?.imported || 0} expenses imported.`);
    } catch (err) {
      console.error(err);
      alert('Import failed: ' + (err.response?.data?.error || err.message));
    }
    setImporting(false);
  };

  const handleApproveAnomaly = async (reportId, anomalyId, status) => {
    try {
      await reviewAnomaly(groupId, reportId, anomalyId, status);
      const r = await getImportReports(groupId);
      setImportReports(r.data);
    } catch (err) {
      console.error(err);
    }
  };

  // Quick settle from simplified debts
  const handleQuickSettle = (debt) => {
    setSettlePreFill({
      from_user_id: String(debt.from_id),
      to_user_id: String(debt.to_id),
      amount: String(debt.amount),
    });
    setShowSettleModal(true);
  };

  if (loading) return <div className="loading"><div className="spinner" /> Loading...</div>;
  if (!group) return <div className="empty-state"><h3>Group not found</h3></div>;

  const activeMembers = members.filter(m => !m.left_at);

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to="/" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.85rem' }}>
            ← Back to Groups
          </Link>
          <h1 className="page-title" style={{ marginTop: 8 }}>{group.name}</h1>
          {group.description && <p className="page-subtitle">{group.description}</p>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="badge badge-blue" style={{ padding: '6px 14px', fontSize: '0.78rem' }}>
            {group.default_currency}
          </span>
          <span className="badge badge-gray" style={{ padding: '6px 14px', fontSize: '0.78rem' }}>
            {members.length} members
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {[
          { key: 'balances', label: 'Balances' },
          { key: 'expenses', label: 'Expenses', count: expenses.length },
          { key: 'settlements', label: 'Settlements', count: settlements.length },
          { key: 'members', label: 'Members', count: members.length },
          { key: 'import', label: 'Import' },
        ].map((t) => (
          <button
            key={t.key}
            id={`tab-${t.key}`}
            className={`tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            {t.count != null && <span className="tab-count">{t.count}</span>}
          </button>
        ))}
      </div>

      {/* ── BALANCES TAB ─────────────────────────────────── */}
      {tab === 'balances' && <BalancesTab
        balances={balances}
        drillUser={drillUser}
        setDrillUser={setDrillUser}
        onQuickSettle={handleQuickSettle}
      />}

      {/* ── EXPENSES TAB ─────────────────────────────────── */}
      {tab === 'expenses' && <ExpensesTab
        expenses={expenses}
        expandedExpense={expandedExpense}
        setExpandedExpense={setExpandedExpense}
        onAdd={() => setShowExpenseModal(true)}
      />}

      {/* ── SETTLEMENTS TAB ──────────────────────────────── */}
      {tab === 'settlements' && <SettlementsTab
        settlements={settlements}
        onAdd={() => { setSettlePreFill(null); setShowSettleModal(true); }}
      />}

      {/* ── MEMBERS TAB ──────────────────────────────────── */}
      {tab === 'members' && <MembersTab
        members={members}
        groupId={groupId}
        onRefresh={fetchAll}
        onShowAdd={() => setShowMemberModal(true)}
      />}

      {/* ── IMPORT TAB ───────────────────────────────────── */}
      {tab === 'import' && <ImportTab
        importing={importing}
        importResult={importResult}
        importReports={importReports}
        members={members}
        missingPayerAssignments={missingPayerAssignments}
        setMissingPayerAssignments={setMissingPayerAssignments}
        handleFileUpload={handleFileUpload}
        handleImportConfirm={handleImportConfirm}
        handleApproveAnomaly={handleApproveAnomaly}
        setImportResult={setImportResult}
      />}

      {/* ── MODALS ───────────────────────────────────────── */}
      {showExpenseModal && (
        <ExpenseModal
          groupId={groupId}
          members={members}
          onClose={() => { setShowExpenseModal(false); fetchAll(); }}
        />
      )}
      {showSettleModal && (
        <SettleModal
          groupId={groupId}
          members={members}
          preFill={settlePreFill}
          onClose={() => { setShowSettleModal(false); setSettlePreFill(null); fetchAll(); }}
        />
      )}
      {showMemberModal && (
        <AddMemberModal
          groupId={groupId}
          existingMembers={members}
          onClose={() => { setShowMemberModal(false); fetchAll(); }}
        />
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   BALANCES TAB
   ═══════════════════════════════════════════════════════ */

function BalancesTab({ balances, drillUser, setDrillUser, onQuickSettle }) {
  if (!balances) return <div className="empty-state"><h3>No balance data</h3></div>;

  return (
    <div>
      {/* Net balances */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Net Balances</h2>
            <div className="card-subtitle">Positive = others owe you · Negative = you owe others</div>
          </div>
          <span className="badge badge-blue">All currencies → INR</span>
        </div>
        {balances.balances?.map((b) => (
          <div className="balance-bar" key={b.user_id}>
            <div className={`avatar ${getAvatarClass(b.user_name)}`}>
              {(b.user_name || '?')[0]}
            </div>
            <span className="balance-name">{b.user_name}</span>
            <span
              className={`balance-amount ${parseFloat(b.net_balance) >= 0 ? 'stat-positive' : 'stat-negative'}`}
            >
              {parseFloat(b.net_balance) >= 0 ? '+' : '-'}
              {formatCurrency(b.net_balance)}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setDrillUser(drillUser === b.user_id ? null : b.user_id)}
            >
              {drillUser === b.user_id ? 'Hide' : 'Details'}
            </button>
          </div>
        ))}
      </div>

      {/* Drill-down - Rohan's view */}
      {drillUser && balances.balances && (
        <DrillDown balances={balances} drillUser={drillUser} />
      )}

      {/* Simplified debts - Aisha's view */}
      {balances.simplified_debts?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Simplified Debts</h2>
              <div className="card-subtitle">Minimum transactions to settle all balances</div>
            </div>
            <span className="badge badge-green">{balances.simplified_debts.length} transaction{balances.simplified_debts.length !== 1 ? 's' : ''}</span>
          </div>
          {balances.simplified_debts.map((d, i) => (
            <div className="debt-item" key={i}>
              <div className={`avatar ${getAvatarClass(d.from_name)}`} style={{ width: 30, height: 30, fontSize: '0.75rem' }}>
                {d.from_name[0]}
              </div>
              <span style={{ fontWeight: 600 }}>{d.from_name}</span>
              <span className="debt-arrow">→</span>
              <div className={`avatar ${getAvatarClass(d.to_name)}`} style={{ width: 30, height: 30, fontSize: '0.75rem' }}>
                {d.to_name[0]}
              </div>
              <span style={{ fontWeight: 600 }}>{d.to_name}</span>
              <span className="debt-amount">{formatCurrency(d.amount)}</span>
              <button
                className="btn btn-success btn-sm debt-settle-btn"
                onClick={() => onQuickSettle(d)}
              >
                Settle
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ── Drill Down ─── */

function DrillDown({ balances, drillUser }) {
  const userBalance = balances.balances.find(b => b.user_id === drillUser);
  if (!userBalance) return null;

  const details = userBalance.expense_details || [];

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <div className="card-header">
        <div>
          <h2 className="card-title">
            Expense Breakdown — {userBalance.user_name}
          </h2>
          <div className="card-subtitle">Every expense contributing to this balance</div>
        </div>
        <span className="badge badge-orange">Rohan's View</span>
      </div>

      {/* Summary stats */}
      <div className="grid-3" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Paid</div>
          <div className="stat-value stat-positive">{formatCurrency(userBalance.total_paid)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Owed</div>
          <div className="stat-value stat-negative">{formatCurrency(userBalance.total_owed)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Net Balance</div>
          <div className={`stat-value ${parseFloat(userBalance.net_balance) >= 0 ? 'stat-positive' : 'stat-negative'}`}>
            {parseFloat(userBalance.net_balance) >= 0 ? '+' : '-'}{formatCurrency(userBalance.net_balance)}
          </div>
        </div>
      </div>

      {details.length > 0 ? (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Paid By</th>
                <th>Total</th>
                <th>Your Share</th>
                <th>Currency</th>
              </tr>
            </thead>
            <tbody>
              {details.map((d, i) => (
                <tr key={i}>
                  <td>{formatDate(d.date)}</td>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{d.description}</td>
                  <td>{d.paid_by}</td>
                  <td>{formatCurrency(d.total_amount)}</td>
                  <td style={{
                    fontWeight: 600,
                    color: parseFloat(d.your_share) > 0 ? 'var(--red)' : 'var(--green)'
                  }}>
                    {formatCurrency(d.your_share)}
                  </td>
                  <td>
                    <span className={`badge ${d.currency === 'USD' ? 'badge-cyan' : 'badge-blue'}`}>
                      {d.currency}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p style={{ color: 'var(--text-muted)' }}>No expense details available. Import data to see drill-down.</p>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   EXPENSES TAB
   ═══════════════════════════════════════════════════════ */

function ExpensesTab({ expenses, expandedExpense, setExpandedExpense, onAdd }) {
  return (
    <div>
      <div className="action-bar">
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {expenses.length} expense{expenses.length !== 1 ? 's' : ''}
        </div>
        <button id="add-expense-btn" className="btn btn-primary" onClick={onAdd}>
          + Add Expense
        </button>
      </div>

      {expenses.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.4 }}>💰</div>
          <h3>No expenses yet</h3>
          <p>Add expenses manually or import from CSV</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Paid By</th>
                  <th>Amount</th>
                  <th>Split</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((exp) => (
                  <>
                    <tr key={exp.id} style={{ cursor: 'pointer' }} onClick={() => setExpandedExpense(expandedExpense === exp.id ? null : exp.id)}>
                      <td>{formatDate(exp.expense_date)}</td>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{exp.description}</td>
                      <td>{exp.paid_by_name || exp.paid_by_user?.name || '—'}</td>
                      <td style={{ fontWeight: 600 }}>
                        {formatCurrency(exp.amount, exp.currency)}
                      </td>
                      <td><span className="badge badge-gray">{exp.split_type}</span></td>
                      <td>
                        <span className={`badge ${
                          exp.status === 'active' ? 'badge-green' :
                          exp.status === 'skipped' ? 'badge-red' :
                          exp.status === 'needs_review' ? 'badge-orange' : 'badge-gray'
                        }`}>
                          {exp.status}
                        </span>
                      </td>
                      <td>
                        {exp.currency === 'USD' && (
                          <span className="badge badge-cyan" title="Multi-currency expense">USD</span>
                        )}
                      </td>
                    </tr>
                    {/* Expanded detail row */}
                    {expandedExpense === exp.id && (
                      <tr key={`${exp.id}-detail`}>
                        <td colSpan={7} style={{ padding: 0 }}>
                          <div className="expense-detail">
                            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 12 }}>
                              {exp.notes && (
                                <div>
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Notes</span>
                                  <div style={{ fontSize: '0.85rem', marginTop: 4 }}>{exp.notes}</div>
                                </div>
                              )}
                              {exp.import_row_number && (
                                <div>
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>CSV Row</span>
                                  <div style={{ fontSize: '0.85rem', marginTop: 4 }}>#{exp.import_row_number}</div>
                                </div>
                              )}
                            </div>
                            {exp.splits && exp.splits.length > 0 && (
                              <div>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Split Details</span>
                                <div className="expense-splits-list">
                                  {exp.splits.map((s, i) => (
                                    <div className="expense-split-chip" key={i}>
                                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                        {s.user?.name || '—'}
                                      </span>
                                      <span>{formatCurrency(s.amount, exp.currency)}</span>
                                      {s.percentage && <span style={{ color: 'var(--text-muted)' }}>({s.percentage}%)</span>}
                                      {s.share_value && <span style={{ color: 'var(--text-muted)' }}>({s.share_value}x)</span>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   SETTLEMENTS TAB
   ═══════════════════════════════════════════════════════ */

function SettlementsTab({ settlements, onAdd }) {
  return (
    <div>
      <div className="action-bar">
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {settlements.length} settlement{settlements.length !== 1 ? 's' : ''}
        </div>
        <button id="add-settlement-btn" className="btn btn-primary" onClick={onAdd}>
          + Record Payment
        </button>
      </div>

      {settlements.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.4 }}>🤝</div>
          <h3>No settlements yet</h3>
          <p>Record payments between members to settle debts</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table>
              <thead>
                <tr><th>Date</th><th>From</th><th></th><th>To</th><th>Amount</th><th>Notes</th></tr>
              </thead>
              <tbody>
                {settlements.map((s) => (
                  <tr key={s.id}>
                    <td>{formatDate(s.settlement_date)}</td>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div className={`avatar ${getAvatarClass(s.from_user_name || s.from_user_data?.name)}`}
                          style={{ width: 26, height: 26, fontSize: '0.7rem' }}>
                          {(s.from_user_name || s.from_user_data?.name || '?')[0]}
                        </div>
                        {s.from_user_name || s.from_user_data?.name}
                      </div>
                    </td>
                    <td style={{ color: 'var(--accent)', fontSize: '1.1rem' }}>→</td>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div className={`avatar ${getAvatarClass(s.to_user_name || s.to_user_data?.name)}`}
                          style={{ width: 26, height: 26, fontSize: '0.7rem' }}>
                          {(s.to_user_name || s.to_user_data?.name || '?')[0]}
                        </div>
                        {s.to_user_name || s.to_user_data?.name}
                      </div>
                    </td>
                    <td style={{ fontWeight: 600 }}>{formatCurrency(s.amount, s.currency)}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>{s.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   MEMBERS TAB
   ═══════════════════════════════════════════════════════ */

function MembersTab({ members, groupId, onRefresh, onShowAdd }) {
  const [editingMember, setEditingMember] = useState(null);
  const [leftDate, setLeftDate] = useState('');

  const handleSetLeftDate = async (membership) => {
    if (!leftDate) return;
    try {
      await updateMembership(groupId, membership.id, { left_at: leftDate });
      setEditingMember(null);
      setLeftDate('');
      onRefresh();
    } catch (err) {
      alert('Error: ' + (err.response?.data?.error || err.message));
    }
  };

  return (
    <div>
      <div className="action-bar">
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {members.filter(m => !m.left_at).length} active · {members.filter(m => m.left_at).length} departed
        </div>
        <button id="add-member-btn" className="btn btn-primary" onClick={onShowAdd}>
          + Add Member
        </button>
      </div>

      <div className="card">
        {members.map((m) => (
          <div className="balance-bar" key={m.id}>
            <div className={`avatar ${getAvatarClass(m.user_name || m.user?.name)}`}>
              {(m.user_name || m.user?.name || '?')[0]}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{m.user_name || m.user?.name}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Joined: {formatDate(m.joined_at)}
                {m.left_at && <span style={{ color: 'var(--red)', marginLeft: 8 }}>Left: {formatDate(m.left_at)}</span>}
              </div>
            </div>
            <span className="badge badge-gray" style={{ marginRight: 8 }}>{m.role}</span>
            <span className={`badge ${m.left_at ? 'badge-red' : 'badge-green'}`}>
              {m.left_at ? 'Departed' : <><span className="pulse-dot" style={{ marginRight: 4 }} /> Active</>}
            </span>
            {!m.left_at && (
              <>
                {editingMember === m.id ? (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 8 }}>
                    <input
                      type="date"
                      className="form-input"
                      style={{ padding: '6px 10px', width: 140, fontSize: '0.82rem' }}
                      value={leftDate}
                      onChange={(e) => setLeftDate(e.target.value)}
                    />
                    <button className="btn btn-danger btn-xs" onClick={() => handleSetLeftDate(m)}>Set</button>
                    <button className="btn btn-ghost btn-xs" onClick={() => setEditingMember(null)}>×</button>
                  </div>
                ) : (
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginLeft: 8 }}
                    onClick={() => { setEditingMember(m.id); setLeftDate(''); }}
                  >
                    Set departure
                  </button>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   IMPORT TAB
   ═══════════════════════════════════════════════════════ */

function ImportTab({
  importing, importResult, importReports, members,
  missingPayerAssignments, setMissingPayerAssignments,
  handleFileUpload, handleImportConfirm, handleApproveAnomaly,
  setImportResult,
}) {
  return (
    <div>
      {/* File upload */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Import CSV</h2>
            <div className="card-subtitle">Upload expenses_export.csv to detect anomalies and import data</div>
          </div>
          <span className="badge badge-orange">Meera's Approval Workflow</span>
        </div>

        <div className="inline-alert inline-alert-info" style={{ marginBottom: 16 }}>
          <span className="inline-alert-icon">ℹ️</span>
          <span>The importer automatically detects duplicates, wrong dates, missing fields, settlements logged as expenses, and 12+ other anomaly types. All changes require your review before being applied.</span>
        </div>

        <div
          className="file-drop"
          onClick={() => document.getElementById('csv-input').click()}
        >
          <div className="file-drop-icon">📄</div>
          <div className="file-drop-title">
            {importing ? 'Processing...' : 'Click to upload expenses_export.csv'}
          </div>
          <div className="file-drop-hint">
            CSV files are parsed, anomalies detected, and previewed before import
          </div>
        </div>
        <input
          type="file"
          id="csv-input"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={handleFileUpload}
        />
      </div>

      {/* Import Preview */}
      {importResult && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h2 className="card-title">Import Preview</h2>
            {importResult.report_id && <span className="badge badge-green">Imported</span>}
          </div>

          {/* Summary stats */}
          <div className="import-summary-grid">
            <div className="import-summary-item">
              <div className="value">{importResult.summary?.total_rows || 0}</div>
              <div className="label">Total Rows</div>
            </div>
            <div className="import-summary-item">
              <div className="value" style={{ color: 'var(--green)' }}>
                {importResult.summary?.active_rows || importResult.summary?.imported || 0}
              </div>
              <div className="label">Active</div>
            </div>
            <div className="import-summary-item">
              <div className="value" style={{ color: 'var(--red)' }}>
                {importResult.summary?.skipped_rows || importResult.summary?.skipped || 0}
              </div>
              <div className="label">Skipped</div>
            </div>
            <div className="import-summary-item">
              <div className="value" style={{ color: 'var(--purple)' }}>
                {importResult.summary?.settlement_rows || 0}
              </div>
              <div className="label">Settlements</div>
            </div>
            <div className="import-summary-item">
              <div className="value" style={{ color: 'var(--orange)' }}>
                {importResult.summary?.total_anomalies || importResult.anomalies?.length || 0}
              </div>
              <div className="label">Anomalies</div>
            </div>
          </div>

          {/* Anomaly list */}
          {importResult.anomalies?.length > 0 && (
            <div>
              <h3 className="section-title">
                Detected Anomalies ({importResult.anomalies.length})
              </h3>
              <div className="section-subtitle">
                Review each anomaly before confirming import. The importer has auto-corrected obvious issues and flagged ambiguous ones for your approval.
              </div>
              {importResult.anomalies.map((a, i) => (
                <AnomalyCard
                  key={i}
                  anomaly={a}
                  members={members}
                  missingPayerAssignments={missingPayerAssignments}
                  setMissingPayerAssignments={setMissingPayerAssignments}
                />
              ))}
            </div>
          )}

          {/* Import button */}
          {importResult.summary && !importResult.report_id && (
            <div className="modal-footer" style={{ marginTop: 24 }}>
              <button className="btn btn-secondary" onClick={() => setImportResult(null)}>
                Cancel
              </button>
              <button id="confirm-import-btn" className="btn btn-primary" onClick={handleImportConfirm} disabled={importing}>
                {importing ? 'Importing...' : `Confirm & Import (${importResult.summary.active_rows || 0} expenses)`}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Past import reports */}
      {importReports.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Import History</h2>
            <span className="badge badge-gray">{importReports.length} report{importReports.length !== 1 ? 's' : ''}</span>
          </div>
          {importReports.map((report) => (
            <ImportReportCard
              key={report.id}
              report={report}
              handleApproveAnomaly={handleApproveAnomaly}
            />
          ))}
        </div>
      )}
    </div>
  );
}


/* ── Anomaly Card ─── */

function AnomalyCard({ anomaly: a, members, missingPayerAssignments, setMissingPayerAssignments }) {
  return (
    <div className="anomaly-item">
      <div className="anomaly-header">
        <span className="anomaly-row">Row #{a.row_number}</span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className={`badge ${
            a.severity === 'error' ? 'badge-red' :
            a.severity === 'warning' ? 'badge-orange' : 'badge-blue'
          }`}>
            {a.severity}
          </span>
          <span className="badge badge-gray">{a.category}</span>
          <span className={`badge ${
            a.status === 'needs_review' ? 'badge-orange' :
            a.status === 'auto_resolved' ? 'badge-green' :
            a.status === 'user_approved' ? 'badge-green' : 'badge-red'
          }`}>
            {a.status?.replace('_', ' ')}
          </span>
          {a.action_taken && (
            <span className="badge badge-purple">{a.action_taken.replace('_', ' ')}</span>
          )}
        </div>
      </div>
      <div className="anomaly-desc">{a.description}</div>
      {a.original_value && (
        <div className="anomaly-correction">
          <strong>Original:</strong> {a.original_value}
          {a.corrected_value && (
            <> → <strong>Corrected:</strong> <span style={{ color: 'var(--green)' }}>{a.corrected_value}</span></>
          )}
        </div>
      )}
      {/* Payer assignment for missing_payer */}
      {a.category === 'missing_payer' && (
        <div className="payer-assignment">
          <div className="payer-assignment-title">
            Who paid for this? (required to import this row)
          </div>
          <div className="payer-assignment-row">
            <select
              className="form-select"
              style={{ flex: 1, padding: '8px 12px', fontSize: '0.85rem' }}
              value={missingPayerAssignments[a.row_number] || ''}
              onChange={e => setMissingPayerAssignments(prev => ({ ...prev, [a.row_number]: e.target.value }))}
            >
              <option value="">Select who paid...</option>
              {members.filter(m => !m.left_at).map(m => (
                <option key={m.user_id || m.user?.id} value={m.user_name || m.user?.name}>
                  {m.user_name || m.user?.name}
                </option>
              ))}
            </select>
            {missingPayerAssignments[a.row_number] && (
              <span className="badge badge-green">
                ✓ {missingPayerAssignments[a.row_number]}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


/* ── Import Report Card ─── */

function ImportReportCard({ report, handleApproveAnomaly }) {
  const [expanded, setExpanded] = useState(false);
  const pendingCount = report.anomalies?.filter(a => a.status === 'needs_review').length || 0;

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 0', cursor: 'pointer', borderBottom: '1px solid var(--border)'
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <span style={{ fontSize: '1.1rem' }}>{expanded ? '▾' : '▸'}</span>
        <span style={{ fontWeight: 600 }}>Report #{report.id}</span>
        <span className="badge badge-gray">{report.filename}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {report.imported_count} imported · {report.skipped_count} skipped
        </span>
        {pendingCount > 0 && (
          <span className="badge badge-orange">{pendingCount} pending review</span>
        )}
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {report.created_at}
        </span>
      </div>
      {expanded && report.anomalies?.map((a) => (
        <div className="anomaly-item" key={a.id} style={{ marginLeft: 24, marginTop: 8 }}>
          <div className="anomaly-header">
            <span className="anomaly-row">Row #{a.row_number}</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <span className={`badge ${
                a.severity === 'error' ? 'badge-red' :
                a.severity === 'warning' ? 'badge-orange' : 'badge-blue'
              }`}>
                {a.severity}
              </span>
              <span className="badge badge-gray">{a.category}</span>
              <span className={`badge ${
                a.status === 'needs_review' ? 'badge-orange' :
                a.status === 'user_approved' ? 'badge-green' : 'badge-red'
              }`}>
                {a.status?.replace('_', ' ')}
              </span>
            </div>
          </div>
          <div className="anomaly-desc">{a.description}</div>
          {a.status === 'needs_review' && (
            <div className="anomaly-actions">
              <button
                className="btn btn-success btn-sm"
                onClick={() => handleApproveAnomaly(report.id, a.id, 'user_approved')}
              >
                ✓ Approve
              </button>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => handleApproveAnomaly(report.id, a.id, 'user_rejected')}
              >
                ✗ Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   EXPENSE MODAL — Supports all 4 split types
   ═══════════════════════════════════════════════════════ */

function ExpenseModal({ groupId, members, onClose }) {
  const allMembers = members; // Include departed for historical lookup
  const activeMembers = members.filter(m => !m.left_at);

  const [form, setForm] = useState({
    description: '',
    amount: '',
    currency: 'INR',
    split_type: 'equal',
    expense_date: new Date().toISOString().split('T')[0],
    paid_by_id: '',
    notes: '',
  });

  // Participant selection (checkbox chips)
  const [selectedParticipants, setSelectedParticipants] = useState(
    activeMembers.map(m => m.user_id || m.user?.id)
  );

  // Split details for unequal/percentage/share
  const [splitDetails, setSplitDetails] = useState({});

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const toggleParticipant = (userId) => {
    setSelectedParticipants(prev =>
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const updateSplitDetail = (userId, value) => {
    setSplitDetails(prev => ({ ...prev, [userId]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.paid_by_id) {
      setError('Please select who paid');
      return;
    }
    if (selectedParticipants.length === 0) {
      setError('Select at least one participant');
      return;
    }
    if (!form.amount || parseFloat(form.amount) <= 0) {
      setError('Amount must be greater than 0');
      return;
    }

    // Validate split details for non-equal types
    if (form.split_type !== 'equal') {
      const missingDetails = selectedParticipants.filter(id => !splitDetails[id] && splitDetails[id] !== 0);
      if (missingDetails.length > 0 && form.split_type !== 'equal') {
        // For percentage/share, we can default missing to 0
        // For unequal, all must be specified
        if (form.split_type === 'unequal' && missingDetails.length > 0) {
          setError('Please specify amounts for all participants');
          return;
        }
      }
    }

    // Validate percentage sum
    if (form.split_type === 'percentage') {
      const total = Object.values(splitDetails).reduce((a, b) => a + (parseFloat(b) || 0), 0);
      if (Math.abs(total - 100) > 5) {
        setError(`Percentages sum to ${total}%, expected close to 100%`);
        return;
      }
    }

    setSaving(true);
    try {
      const payload = {
        description: form.description,
        amount: parseFloat(form.amount),
        currency: form.currency,
        split_type: form.split_type,
        expense_date: form.expense_date,
        paid_by_id: parseInt(form.paid_by_id),
        notes: form.notes,
        split_with: selectedParticipants.map(id => parseInt(id)),
      };

      // Add split details for non-equal types
      if (form.split_type !== 'equal' && Object.keys(splitDetails).length > 0) {
        const details = {};
        for (const id of selectedParticipants) {
          details[String(id)] = parseFloat(splitDetails[id] || 0);
        }
        payload.split_details = details;
      }

      await createExpense(groupId, payload);
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || JSON.stringify(err.response?.data) || err.message);
    }
    setSaving(false);
  };

  const getMemberName = (userId) => {
    const m = allMembers.find(m => (m.user_id || m.user?.id) === userId);
    return m?.user_name || m?.user?.name || 'Unknown';
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <h2 className="modal-title">Add Expense</h2>
        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Description</label>
            <input
              id="expense-description"
              className="form-input"
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="What was this expense for?"
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Amount</label>
              <input
                id="expense-amount"
                className="form-input"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={e => setForm({ ...form, amount: e.target.value })}
                placeholder="0.00"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Currency</label>
              <select
                id="expense-currency"
                className="form-select"
                value={form.currency}
                onChange={e => setForm({ ...form, currency: e.target.value })}
              >
                <option value="INR">INR (₹)</option>
                <option value="USD">USD ($)</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Paid By</label>
              <select
                id="expense-paid-by"
                className="form-select"
                value={form.paid_by_id}
                onChange={e => setForm({ ...form, paid_by_id: e.target.value })}
                required
              >
                <option value="">Select who paid...</option>
                {allMembers.map(m => {
                  const id = m.user_id || m.user?.id;
                  const name = m.user_name || m.user?.name;
                  return <option key={id} value={id}>{name}{m.left_at ? ' (departed)' : ''}</option>;
                })}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Date</label>
              <input
                id="expense-date"
                className="form-input"
                type="date"
                value={form.expense_date}
                onChange={e => setForm({ ...form, expense_date: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Split Type</label>
            <select
              id="expense-split-type"
              className="form-select"
              value={form.split_type}
              onChange={e => { setForm({ ...form, split_type: e.target.value }); setSplitDetails({}); }}
            >
              <option value="equal">Equal — Split evenly</option>
              <option value="unequal">Unequal — Fixed amounts per person</option>
              <option value="percentage">Percentage — % based split</option>
              <option value="share">Share/Ratio — e.g., 1:2:1</option>
            </select>
          </div>

          {/* Participant selection */}
          <div className="form-group">
            <label className="form-label">
              Split With ({selectedParticipants.length} selected)
            </label>
            <div className="checkbox-group">
              {allMembers.map(m => {
                const id = m.user_id || m.user?.id;
                const name = m.user_name || m.user?.name;
                const selected = selectedParticipants.includes(id);
                return (
                  <label
                    key={id}
                    className={`checkbox-chip ${selected ? 'selected' : ''}`}
                    onClick={() => toggleParticipant(id)}
                  >
                    <input type="checkbox" checked={selected} readOnly />
                    {name}{m.left_at ? ' ⚠' : ''}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Split detail inputs (for non-equal types) */}
          {form.split_type !== 'equal' && selectedParticipants.length > 0 && (
            <div className="split-inputs">
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                {form.split_type === 'unequal' ? 'Amount per person' :
                 form.split_type === 'percentage' ? 'Percentage per person' :
                 'Share ratio per person'}
              </div>
              {selectedParticipants.map(userId => (
                <div className="split-input-row" key={userId}>
                  <span className="split-input-label">{getMemberName(userId)}</span>
                  <input
                    className="split-input-field"
                    type="number"
                    step={form.split_type === 'share' ? '1' : '0.01'}
                    min="0"
                    placeholder={form.split_type === 'percentage' ? '25' : form.split_type === 'share' ? '1' : '0.00'}
                    value={splitDetails[userId] || ''}
                    onChange={e => updateSplitDetail(userId, e.target.value)}
                  />
                  <span className="split-input-suffix">
                    {form.split_type === 'percentage' ? '%' :
                     form.split_type === 'share' ? 'x' :
                     form.currency === 'USD' ? '$' : '₹'}
                  </span>
                </div>
              ))}
              {form.split_type === 'percentage' && (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 8 }}>
                  Total: {Object.values(splitDetails).reduce((a, b) => a + (parseFloat(b) || 0), 0).toFixed(1)}%
                  {Math.abs(Object.values(splitDetails).reduce((a, b) => a + (parseFloat(b) || 0), 0) - 100) > 0.1 && (
                    <span style={{ color: 'var(--orange)', marginLeft: 8 }}>
                      (will be normalized to 100%)
                    </span>
                  )}
                </div>
              )}
              {form.split_type === 'unequal' && form.amount && (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 8 }}>
                  Total entered: {form.currency === 'USD' ? '$' : '₹'}
                  {Object.values(splitDetails).reduce((a, b) => a + (parseFloat(b) || 0), 0).toFixed(2)}
                  {' / '}
                  {form.currency === 'USD' ? '$' : '₹'}{parseFloat(form.amount).toFixed(2)}
                </div>
              )}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Notes (optional)</label>
            <textarea
              id="expense-notes"
              className="form-textarea"
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="Any additional notes..."
              style={{ minHeight: 60 }}
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button id="expense-submit" type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Add Expense'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   SETTLEMENT MODAL
   ═══════════════════════════════════════════════════════ */

function SettleModal({ groupId, members, preFill, onClose }) {
  const [form, setForm] = useState({
    from_user_id: preFill?.from_user_id || '',
    to_user_id: preFill?.to_user_id || '',
    amount: preFill?.amount || '',
    settlement_date: new Date().toISOString().split('T')[0],
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (form.from_user_id === form.to_user_id) {
      setError('From and To must be different people');
      return;
    }

    setSaving(true);
    try {
      await createSettlement(groupId, {
        from_user_id: parseInt(form.from_user_id),
        to_user_id: parseInt(form.to_user_id),
        amount: parseFloat(form.amount),
        settlement_date: form.settlement_date,
        notes: form.notes,
      });
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
    setSaving(false);
  };

  const fromName = members.find(m => String(m.user_id || m.user?.id) === form.from_user_id);
  const toName = members.find(m => String(m.user_id || m.user?.id) === form.to_user_id);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2 className="modal-title">Record Payment</h2>
        {error && <div className="error-msg">{error}</div>}

        {preFill && (
          <div className="inline-alert inline-alert-info" style={{ marginBottom: 16 }}>
            <span className="inline-alert-icon">💡</span>
            <span>Pre-filled from simplified debts. Adjust if needed.</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">From (Who Paid)</label>
              <select
                id="settle-from"
                className="form-select"
                value={form.from_user_id}
                onChange={e => setForm({ ...form, from_user_id: e.target.value })}
                required
              >
                <option value="">Select...</option>
                {members.map(m => {
                  const id = m.user_id || m.user?.id;
                  const name = m.user_name || m.user?.name;
                  return <option key={id} value={id}>{name}</option>;
                })}
              </select>
            </div>
            <div style={{ padding: '0 8px', fontSize: '1.5rem', color: 'var(--accent)', alignSelf: 'center', paddingTop: 24 }}>→</div>
            <div className="form-group">
              <label className="form-label">To (Who Received)</label>
              <select
                id="settle-to"
                className="form-select"
                value={form.to_user_id}
                onChange={e => setForm({ ...form, to_user_id: e.target.value })}
                required
              >
                <option value="">Select...</option>
                {members.map(m => {
                  const id = m.user_id || m.user?.id;
                  const name = m.user_name || m.user?.name;
                  return <option key={id} value={id}>{name}</option>;
                })}
              </select>
            </div>
          </div>

          {/* Visual summary */}
          {fromName && toName && form.amount && (
            <div style={{
              padding: '16px',
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              marginBottom: 20,
              textAlign: 'center',
            }}>
              <span style={{ fontWeight: 600 }}>{fromName.user_name || fromName.user?.name}</span>
              <span style={{ margin: '0 12px', color: 'var(--accent)' }}>pays</span>
              <span style={{ fontWeight: 600 }}>{toName.user_name || toName.user?.name}</span>
              <span style={{ margin: '0 12px', color: 'var(--accent)' }}>→</span>
              <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--green)' }}>
                ₹{parseFloat(form.amount).toLocaleString('en-IN')}
              </span>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Amount (₹)</label>
              <input
                id="settle-amount"
                className="form-input"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={e => setForm({ ...form, amount: e.target.value })}
                placeholder="0.00"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Date</label>
              <input
                id="settle-date"
                className="form-input"
                type="date"
                value={form.settlement_date}
                onChange={e => setForm({ ...form, settlement_date: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Notes (optional)</label>
            <input
              id="settle-notes"
              className="form-input"
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="e.g., Paid via UPI"
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button id="settle-submit" type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Record Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   ADD MEMBER MODAL
   ═══════════════════════════════════════════════════════ */

function AddMemberModal({ groupId, existingMembers, onClose }) {
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [joinedAt, setJoinedAt] = useState(new Date().toISOString().split('T')[0]);
  const [role, setRole] = useState('member');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadingUsers, setLoadingUsers] = useState(true);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const res = await getUsers();
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoadingUsers(false);
  };

  // Filter out users already in the group
  const existingUserIds = existingMembers.map(m => m.user_id || m.user?.id);
  const availableUsers = users.filter(u => !existingUserIds.includes(u.id));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUserId) {
      setError('Please select a user');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await addMember(groupId, {
        user_id: parseInt(selectedUserId),
        joined_at: joinedAt,
        role,
      });
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
    setSaving(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2 className="modal-title">Add Member</h2>
        {error && <div className="error-msg">{error}</div>}

        {loadingUsers ? (
          <div className="loading"><div className="spinner" /> Loading users...</div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Select User</label>
              <select
                id="member-user-select"
                className="form-select"
                value={selectedUserId}
                onChange={e => setSelectedUserId(e.target.value)}
                required
              >
                <option value="">Choose a user...</option>
                {availableUsers.map(u => (
                  <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                ))}
              </select>
              {availableUsers.length === 0 && (
                <div className="form-hint" style={{ color: 'var(--orange)' }}>
                  All registered users are already members. Register a new user first.
                </div>
              )}
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Joined Date</label>
                <input
                  id="member-joined-date"
                  className="form-input"
                  type="date"
                  value={joinedAt}
                  onChange={e => setJoinedAt(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Role</label>
                <select
                  id="member-role-select"
                  className="form-select"
                  value={role}
                  onChange={e => setRole(e.target.value)}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button id="member-add-submit" type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Adding...' : 'Add Member'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
