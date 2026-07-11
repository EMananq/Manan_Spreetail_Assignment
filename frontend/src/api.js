import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const login = (email, password) => api.post('/auth/login/', { email, password });
export const register = (name, email, password) => api.post('/auth/register/', { name, email, password });
export const getMe = () => api.get('/auth/me/');
export const getUsers = () => api.get('/auth/users/');

// Groups
export const getGroups = (all = false) => api.get(`/groups/${all ? '?all=true' : ''}`);
export const getGroup = (id) => api.get(`/groups/${id}/`);
export const createGroup = (data) => api.post('/groups/', data);
export const updateGroup = (id, data) => api.put(`/groups/${id}/`, data);
export const deleteGroup = (id) => api.delete(`/groups/${id}/`);

// Members
export const getMembers = (groupId) => api.get(`/groups/${groupId}/members/`);
export const addMember = (groupId, data) => api.post(`/groups/${groupId}/members/`, data);
export const updateMembership = (groupId, membershipId, data) =>
  api.put(`/groups/${groupId}/members/${membershipId}/`, data);

// Expenses
export const getExpenses = (groupId) => api.get(`/groups/${groupId}/expenses/`);
export const createExpense = (groupId, data) => api.post(`/groups/${groupId}/expenses/`, data);

// Settlements
export const getSettlements = (groupId) => api.get(`/groups/${groupId}/settlements/`);
export const createSettlement = (groupId, data) => api.post(`/groups/${groupId}/settlements/`, data);

// Balances
export const getBalances = (groupId) => api.get(`/groups/${groupId}/balances/`);

// Import
export const importCSV = (groupId, csvContent, action = 'preview', payerAssignments = {}) =>
  api.post(`/groups/${groupId}/import/`, { csv_content: csvContent, action, payer_assignments: payerAssignments });

export const getImportReports = (groupId) => api.get(`/groups/${groupId}/import-reports/`);

export const reviewAnomaly = (groupId, reportId, anomalyId, status, notes = '') =>
  api.put(`/groups/${groupId}/import-reports/${reportId}/anomalies/${anomalyId}/`, { status, notes });

export default api;
