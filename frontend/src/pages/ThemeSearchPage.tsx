import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { themeSearchApi } from '../services/api'
import type { ThemeSearch } from '../services/api'

export default function ThemeSearchPage() {
  const navigate = useNavigate()
  const [theme, setTheme] = useState('')
  const [limit, setLimit] = useState(10)
  const [result, setResult] = useState<ThemeSearch | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submitted = useRef(false)

  useEffect(() => {
    let active = true
    themeSearchApi.latest().then((value) => { if (active && value && !submitted.current) { setResult(value); setTheme(value.theme) } }).catch(() => { if (active && !submitted.current) setError('无法加载上次找书结果。') })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!result || !['queued', 'running'].includes(result.status)) return
    let active = true
    const timer = window.setInterval(() => {
      themeSearchApi.get(result.id).then((value) => { if (active) setResult(value) }).catch(() => { if (active) setError('获取找书进度失败，请刷新后重试。') })
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [result?.id, result?.status])

  const busy = loading || !!result && ['queued', 'running'].includes(result.status)
  const submit = async () => {
    if (!theme.trim()) { setError('请输入想研究的主题。'); return }
    submitted.current = true
    setLoading(true)
    setError(null)
    try { setResult(await themeSearchApi.create(theme.trim(), limit)) }
    catch (err: any) { setError(err.response?.data?.detail || '创建找书任务失败，请重试。') }
    finally { setLoading(false) }
  }

  return <div className="px-4 py-6 max-w-5xl mx-auto">
    <h1 className="text-2xl font-bold text-gray-900">按主题找书</h1>
    <p className="text-gray-600 mt-2">输入想研究的话题，查找有主题依据的外文作品，再选择一本继续研究和生成播客稿。</p>
    <div className="bg-white shadow rounded-lg p-6 mt-6">
      <label className="block text-sm font-medium text-gray-700">研究主题
        <input value={theme} onChange={(event) => setTheme(event.target.value)} maxLength={200} onKeyDown={(event) => { if (event.key === 'Enter' && !busy) submit() }} placeholder="例如：死亡与生命意义、人工智能与人类关系" className="mt-2 w-full rounded-md border px-3 py-2" />
      </label>
      <div className="flex flex-wrap items-end gap-4 mt-4">
        <label className="text-sm text-gray-700">最多返回<select value={limit} onChange={(event) => setLimit(Number(event.target.value))} className="ml-2 rounded-md border px-3 py-2">{Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1} 本</option>)}</select></label>
        <button onClick={submit} disabled={busy || !theme.trim()} className="px-4 py-2 rounded-md bg-blue-600 text-white disabled:bg-gray-400">{busy ? '正在找书…' : '搜索相关书籍'}</button>
      </div>
      <p className="text-xs text-gray-500 mt-3">先检索主题证据，再核对书目信息。作者国籍无法确认时会标注“待核实”；证据不足时可能少于所选数量。</p>
      {result && ['queued', 'running'].includes(result.status) && <p className="mt-4 text-sm text-blue-700">{result.current_step || '正在等待任务队列…'}</p>}
      {(error || result?.error_message) && <p className="mt-4 text-sm text-red-700">{error || result?.error_message}</p>}
    </div>
    {result?.status === 'completed' && <div className="mt-6">
      <h2 className="text-lg font-semibold">“{result.theme}”的相关书籍（{result.books.length} 本）</h2>
      {result.books.length === 0 && <p className="bg-amber-50 text-amber-800 rounded p-4 mt-3">暂未找到同时具备主题关联、书目和作者身份依据的书。可以尝试更具体或更宽泛的主题。</p>}
      <div className="space-y-4 mt-4">{result.books.map((book, index) => <article key={book.id} className="bg-white shadow rounded-lg p-5">
        <div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold text-gray-900">{index + 1}. {book.title}</h3><p className="text-sm text-gray-600 mt-1">{book.author} · {book.author_country}{book.isbn ? ` · ISBN ${book.isbn}` : ''}</p></div><button onClick={() => navigate(`/research/${book.id}?theme=${encodeURIComponent(result.theme)}`)} className="px-4 py-2 bg-blue-600 text-white rounded-md">研究这本书</button></div>
        <p className="text-sm text-gray-800 mt-4"><strong>为什么相关：</strong>{book.reasoning}</p>
        <div className="text-sm text-gray-600 mt-3 space-y-2"><p>主题依据：{book.evidence_excerpt} <a className="text-blue-600 underline" href={book.evidence_url} target="_blank" rel="noopener noreferrer">查看来源</a></p><p>作者身份依据：{book.author_evidence_excerpt || '尚未核实作者国籍'} {book.author_evidence_url && <a className="text-blue-600 underline" href={book.author_evidence_url} target="_blank" rel="noopener noreferrer">查看来源</a>}</p><a className="text-blue-600 underline" href={book.catalog_url} target="_blank" rel="noopener noreferrer">查看书目记录</a></div>
      </article>)}</div>
    </div>}
  </div>
}
