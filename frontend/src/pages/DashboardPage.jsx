import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getGroups, createGroup } from '../api';

function getAvatarClass(name) {
  const classes = ['avatar-a', 'avatar-b', 'avatar-c', 'avatar-d', 'avatar-e', 'avatar-f'];
  const idx = (name || '').charCodeAt(0) % classes.length;
  return classes[idx];
}

export default function DashboardPage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newGroup, setNewGroup] = useState({ name: '', description: '', default_currency: 'INR' });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchGroups();
  }, []);

  const fetchGroups = async () => {
    try {
      const res = await getGroups(true);
      setGroups(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      await createGroup(newGroup);
      setShowModal(false);
      setNewGroup({ name: '', description: '', default_currency: 'INR' });
      fetchGroups();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create group');
    }
    setCreating(false);
  };

  if (loading) return <div className="loading"><div className="spinner" /> Loading groups...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Groups</h1>
          <p className="page-subtitle">Manage shared expenses with your flatmates</p>
        </div>
        <button id="create-group-btn" className="btn btn-primary" onClick={() => setShowModal(true)}>
          + New Group
        </button>
      </div>

      {groups.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.4 }}>🏠</div>
          <h3>No groups yet</h3>
          <p>Create a group to start tracking shared expenses</p>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            Create Your First Group
          </button>
        </div>
      ) : (
        <div className="grid-2">
          {groups.map((group) => (
            <Link to={`/groups/${group.id}`} key={group.id} className="group-card">
              <div className="card-title">{group.name}</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 8, minHeight: 20 }}>
                {group.description || 'No description'}
              </p>
              <div style={{ display: 'flex', gap: 12, marginTop: 16, alignItems: 'center' }}>
                <span className="badge badge-blue">{group.default_currency}</span>
                <span className="badge badge-gray">{group.member_count || 0} members</span>
                <span className="badge badge-purple">{group.expense_count || 0} expenses</span>
              </div>
              {/* Member avatars */}
              {group.memberships && group.memberships.length > 0 && (
                <div style={{ display: 'flex', gap: -8, marginTop: 16 }}>
                  {group.memberships.slice(0, 6).map((m, i) => (
                    <div
                      key={m.id}
                      className={`avatar ${getAvatarClass(m.user?.name || m.user_name)}`}
                      style={{ marginLeft: i === 0 ? 0 : -8, zIndex: 6 - i, border: '2px solid var(--bg-card)' }}
                      title={m.user?.name || m.user_name}
                    >
                      {(m.user?.name || m.user_name || '?')[0]}
                    </div>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Create Group Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Create Group</h2>
            {error && <div className="error-msg">{error}</div>}
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Group Name</label>
                <input
                  id="group-name-input"
                  className="form-input"
                  value={newGroup.name}
                  onChange={(e) => setNewGroup({ ...newGroup, name: e.target.value })}
                  placeholder="e.g., Flat Expenses"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  id="group-desc-input"
                  className="form-input"
                  value={newGroup.description}
                  onChange={(e) => setNewGroup({ ...newGroup, description: e.target.value })}
                  placeholder="Shared expenses for our flat"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Default Currency</label>
                <select
                  id="group-currency-select"
                  className="form-select"
                  value={newGroup.default_currency}
                  onChange={(e) => setNewGroup({ ...newGroup, default_currency: e.target.value })}
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button id="group-create-submit" type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? 'Creating...' : 'Create Group'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
