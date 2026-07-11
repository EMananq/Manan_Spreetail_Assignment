import { useState } from 'react';
import { useAuth } from '../AuthContext';

const DEMO_ACCOUNTS = [
  { name: 'Aisha', email: 'aisha@flat.app', password: 'password123' },
  { name: 'Rohan', email: 'rohan@flat.app', password: 'password123' },
  { name: 'Priya', email: 'priya@flat.app', password: 'password123' },
  { name: 'Meera', email: 'meera@flat.app', password: 'password123' },
  { name: 'Dev',   email: 'dev@flat.app',   password: 'password123' },
  { name: 'Sam',   email: 'sam@flat.app',   password: 'password123' },
];

export default function LoginPage() {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await register(name, email, password);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong');
    }
    setLoading(false);
  };

  const fillAccount = (account) => {
    setEmail(account.email);
    setPassword(account.password);
    setIsRegister(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">FairSplit</h1>
        <p className="auth-subtitle">
          {isRegister ? 'Create your account' : 'Welcome back'}
        </p>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                id="register-name"
                type="text"
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              id="login-email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@flat.app"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <button id="login-submit" type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="auth-toggle">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <a onClick={() => { setIsRegister(!isRegister); setError(''); }}>
            {isRegister ? 'Sign in' : 'Register'}
          </a>
        </div>

        {/* Demo Credentials */}
        {!isRegister && (
          <div className="demo-section">
            <div className="demo-title">Demo Accounts — Click to fill</div>
            {DEMO_ACCOUNTS.map((a) => (
              <div
                key={a.email}
                className="demo-row"
                onClick={() => fillAccount(a)}
              >
                <span style={{ fontWeight: 600, fontSize: '0.82rem', minWidth: 60 }}>{a.name}</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.76rem', color: 'var(--text-secondary)', flex: 1 }}>
                  {a.email}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.76rem', color: 'var(--accent-light)' }}>
                  {a.password}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
