import { useState } from 'react'
import { authApi } from '../services/api'

export default function LoginPage({ onLogin }: { onLogin: (user: { id: number; username: string }) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [registering, setRegistering] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true); setError('')
    try { onLogin(registering ? await authApi.register(username, password, code) : await authApi.login(username, password)) }
    catch (err: any) { setError(err.response?.status === 404
      ? '后端仍在运行旧版本，缺少登录接口。请重启后端服务。'
      : err.response?.data?.detail || '登录失败，请检查账号和服务。') }
    finally { setBusy(false) }
  }
  return <div className="max-w-md mx-auto mt-16 bg-white rounded shadow p-6 space-y-4">
    <h1 className="text-xl font-semibold">{registering ? '创建账号' : '登录 Bookcast'}</h1>
    <form onSubmit={submit} className="space-y-3">
      <label className="block text-sm">用户名<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required minLength={3} className="mt-1 w-full border rounded px-3 py-2" /></label>
      <label className="block text-sm">密码（至少 12 位）<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={12} className="mt-1 w-full border rounded px-3 py-2" /></label>
      {registering && <label className="block text-sm">注册口令<input type="password" value={code} onChange={e => setCode(e.target.value)} required className="mt-1 w-full border rounded px-3 py-2" /></label>}
      {error && <p className="text-red-700 text-sm">{error}</p>}
      <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">{busy ? '请稍候…' : registering ? '创建账号' : '登录'}</button>
    </form>
    <button className="text-blue-700 underline text-sm" onClick={() => { setRegistering(!registering); setError('') }}>{registering ? '已有账号？登录' : '没有账号？创建账号'}</button>
  </div>
}
