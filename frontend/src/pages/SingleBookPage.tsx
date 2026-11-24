import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { booksApi } from '../services/api'

type Candidate = Awaited<ReturnType<typeof booksApi.searchSingle>>['books'][number]

export default function SingleBookPage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [books, setBooks] = useState<Candidate[]>([])
  const [references, setReferences] = useState<Array<{ title: string; url: string }>>([])
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const creating = useRef(false)

  const search = async () => {
    if (!title.trim() || loading) return
    setLoading(true)
    setError(null)
    setSearched(false)
    setBooks([])
    setReferences([])
    try {
      const result = await booksApi.searchSingle(title.trim(), author.trim())
      setBooks(result.books)
      setReferences(result.references || [])
      setSearched(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || '书目搜索失败，可填写书名和作者手动继续。')
    } finally { setLoading(false) }
  }

  const choose = async (book: { title: string; author: string; work_key?: string }) => {
    if (creating.current) return
    creating.current = true
    setLoading(true)
    setError(null)
    try {
      const saved = await booksApi.addSingle(book)
      navigate('/research/' + saved.id + '?mode=book')
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存书籍失败，请重试。')
    } finally { creating.current = false; setLoading(false) }
  }

  return <div className="px-4 py-6 max-w-5xl mx-auto">
    <h1 className="text-2xl font-bold text-gray-900">搜索指定书籍</h1>
    <p className="text-gray-600 mt-2">按书名找书，核对作者后研究整本书；研究完成后可生成播客稿。</p>
    <div className="bg-white shadow rounded-lg p-6 mt-6 space-y-3">
      <label className="block text-sm">书名<input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} placeholder="输入原书名" className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label className="block text-sm">作者（可选，用于缩小搜索）<input value={author} onChange={(e) => setAuthor(e.target.value)} maxLength={500} placeholder="例如：Mary Roach" className="mt-1 w-full rounded border px-3 py-2" /></label>
      <button onClick={search} disabled={loading || !title.trim()} className="px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{loading ? '正在处理…' : '搜索书目'}</button>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {searched && !books.length && <p className="text-sm text-amber-700">未能核实书名和作者。{references.length ? '下方有联网搜索资料，请核对后填写作者继续研究。' : '可尝试输入原书名、补充作者，或手动继续研究。'}</p>}
      {searched && <div className="space-y-3">{books.map((book) => <article key={book.work_key || book.title + book.author} className="border rounded p-3 flex justify-between gap-3"><div><strong>{book.title}</strong><p className="text-sm text-gray-600">{book.author}{book.first_published ? ' · ' + book.first_published : ''}</p>{book.source === 'open_library' ? <a href={book.catalog_url || '#'} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 underline">查看 Open Library 记录</a> : <><p className="text-xs text-amber-700">联网搜索候选，未通过馆藏核验；请核对书名与作者</p><a href={book.evidence_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 underline">查看搜索来源</a></>}</div><button onClick={() => choose({ title: book.title, author: book.author, ...(book.work_key ? { work_key: book.work_key } : {}) })} disabled={loading} className="px-3 py-1 rounded bg-blue-600 text-white disabled:bg-gray-400">研究这本书</button></article>)}</div>}
      {searched && references.length > 0 && <details className="text-sm text-gray-600"><summary className="cursor-pointer">查看联网搜索资料（{references.length}）</summary><ul className="mt-2 space-y-1">{references.map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{item.title || item.url}</a></li>)}</ul></details>}
      {title.trim() && author.trim() && <button onClick={() => choose({ title: title.trim(), author: author.trim() })} disabled={loading} className="block text-sm text-blue-700 underline disabled:text-gray-400">找不到书？按所填书名和作者手动继续</button>}
      <p className="text-xs text-gray-500">手动录入未核实书目身份，后续研究仍会尝试核对作者和作品；资料不足时会提示缺口。</p>
    </div>
  </div>
}
