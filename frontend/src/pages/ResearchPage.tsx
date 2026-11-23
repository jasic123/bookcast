import { useState, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { booksApi, healthApi, researchApi } from '../services/api'
import type { Book, Research } from '../types'
import PodcastPanel from './PodcastPanel'

export default function ResearchPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [searchParams] = useSearchParams()
  const [book, setBook] = useState<Book | null>(null)
  const [researches, setResearches] = useState<Research[]>([])
  const [currentResearch, setCurrentResearch] = useState<Research | null>(null)
  const [article, setArticle] = useState<Awaited<ReturnType<typeof researchApi.createReviewArticle>> | null>(null)
  const [articleLoading, setArticleLoading] = useState(false)
  const [articleError, setArticleError] = useState<string | null>(null)
  const [reviews, setReviews] = useState<Awaited<ReturnType<typeof researchApi.getReviewDigest>>['reviews']>([])
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [reviewsError, setReviewsError] = useState(false)
  const [reviewsAttempt, setReviewsAttempt] = useState(0)
  const [loading, setLoading] = useState(false)
  const creating = useRef(false)
  const [error, setError] = useState<string | null>(null)

  // Create research form
  const [themes, setThemes] = useState<string>(() => searchParams.get('theme') || '')
  const [matchMode, setMatchMode] = useState<'any' | 'all'>('any')
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)

  useEffect(() => {
    if (bookId) {
      loadBook(parseInt(bookId))
      loadResearches(parseInt(bookId))
    }
  }, [bookId])

  // Poll job status if there's an active job
  useEffect(() => {
    if (!jobId) return

    let active = true
    let timer: number
    const poll = async () => {
      try {
        const status = await researchApi.getJobStatus(jobId)
        if (!active) return
        setJobStatus(status.status)

        if (status.status === 'finished' || status.status === 'failed') {
          if (bookId) {
            loadResearches(parseInt(bookId))
          }
          setJobId(null)
          return
        }
      } catch (err) {
        console.error('Failed to get job status:', err)
      }
      const issue = await healthApi.checkQueue('research')
      if (active) { setError(issue); timer = window.setTimeout(poll, 2000) }
    }
    timer = window.setTimeout(poll, 2000)

    return () => { active = false; window.clearTimeout(timer) }
  }, [jobId, bookId])

  useEffect(() => {
    if (jobId || !currentResearch || !['queued', 'running'].includes(currentResearch.status)) return
    let active = true
    let timer: number
    const poll = async () => {
      try {
        const value = await researchApi.getResearch(currentResearch.id)
        if (active) setCurrentResearch(value)
      } catch { /* health check below explains the failure */ }
      const issue = await healthApi.checkQueue('research')
      if (active) { setError(issue); timer = window.setTimeout(poll, 3000) }
    }
    timer = window.setTimeout(poll, 3000)
    return () => { active = false; window.clearTimeout(timer) }
  }, [jobId, currentResearch?.id, currentResearch?.status])

  useEffect(() => {
    if (!currentResearch || currentResearch.status !== 'completed') return
    let active = true
    setReviews([])
    setArticle(null)
    setArticleError(null)
    setReviewsError(false)
    setReviewsLoading(true)
    researchApi.getReviewDigest(currentResearch.id).then((result) => {
      if (active) { setReviews(result.reviews); setReviewsError(result.incomplete) }
    }).catch(() => {
      if (active) setReviewsError(true)
    }).finally(() => {
      if (active) setReviewsLoading(false)
    })
    return () => { active = false }
  }, [currentResearch?.id, currentResearch?.status, reviewsAttempt])

  const generateArticle = async () => {
    if (!currentResearch) return
    setArticleLoading(true)
    setArticleError(null)
    try {
      const result = await researchApi.createReviewArticle(currentResearch.id)
      setArticle(result)
    } catch (err: any) {
      setArticleError(err.response?.data?.detail || '综合书评生成失败，请重试。')
    } finally {
      setArticleLoading(false)
    }
  }

  const loadBook = async (id: number) => {
    try {
      const bookData = await booksApi.getBook(id)
      setBook(bookData)
    } catch (err) {
      console.error('Failed to load book:', err)
    }
  }

  const loadResearches = async (id: number) => {
    try {
      const researchData = await researchApi.getResearchForBook(id)
      setResearches(researchData)
      if (researchData.length > 0) {
        setCurrentResearch(researchData[0])
      }
    } catch (err) {
      console.error('Failed to load researches:', err)
    }
  }

  const handleCreateResearch = async () => {
    if (creating.current) return
    if (!bookId || !themes.trim()) {
      setError('请输入至少一个主题')
      return
    }

    creating.current = true
    setLoading(true)
    setError(null)

    try {
      const themeList = themes.split(',').map((t) => t.trim()).filter(Boolean)
      const result = await researchApi.createResearch({
        book_id: parseInt(bookId),
        themes: themeList,
        match_mode: matchMode,
      })

      setJobId(result.job_id)
      setJobStatus('queued')
      setThemes('')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'object' ? `${detail.message}（任务 #${detail.research_id}）` : detail || '创建研究任务失败')
      if (err.response?.status === 409 && bookId) loadResearches(parseInt(bookId))
    } finally {
      creating.current = false
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50'
      case 'running':
        return 'text-blue-600 bg-blue-50'
      case 'failed':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getMatchStatusBadge = (status: string) => {
    switch (status) {
      case 'candidate':
        return 'bg-green-100 text-green-800'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'no_evidence':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getSourceTypeBadge = (type: string) => {
    const badges: Record<string, string> = {
      professional_review: 'bg-purple-100 text-purple-800',
      reader_review: 'bg-blue-100 text-blue-800',
      publisher_description: 'bg-yellow-100 text-yellow-800',
      author_interview: 'bg-green-100 text-green-800',
      news_article: 'bg-indigo-100 text-indigo-800',
      encyclopedia: 'bg-gray-100 text-gray-800',
      other: 'bg-gray-100 text-gray-800',
      irrelevant: 'bg-red-100 text-red-800',
    }
    return badges[type] || 'bg-gray-100 text-gray-800'
  }

  const getSourceTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      professional_review: '专业书评',
      reader_review: '读者评论',
      publisher_description: '出版社简介',
      author_interview: '作者访谈',
      news_article: '新闻报道',
      encyclopedia: '百科信息',
      other: '其他资料',
      irrelevant: '无关内容',
    }
    return labels[type] || type
  }

  if (!book) {
    return <div className="px-4 py-6">加载中...</div>
  }

  return (
    <div className="px-4 py-6">
      {/* Book Info */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{book.title}</h1>
        {book.author && (
          <p className="text-gray-600 mb-2">作者：{book.author}</p>
        )}
        {book.description && (
          <p className="text-gray-700 mt-3">{book.description}</p>
        )}
        <div className="flex space-x-4 mt-4 text-sm text-gray-500">
          {book.isbn && <span>ISBN: {book.isbn}</span>}
          {book.asin && <span>ASIN: {book.asin}</span>}
          {book.rank && <span>排名: #{book.rank}</span>}
        </div>
      </div>

      {/* Create Research */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          创建新研究任务
        </h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              关注主题（用逗号分隔）*
            </label>
            <input
              type="text"
              value={themes}
              onChange={(e) => setThemes(e.target.value)}
              placeholder="例如：死亡, 轮回, 虚拟世界"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading || !!jobId}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              匹配模式
            </label>
            <select
              value={matchMode}
              onChange={(e) => setMatchMode(e.target.value as 'any' | 'all')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading || !!jobId}
            >
              <option value="any">任一主题匹配</option>
              <option value="all">全部主题匹配</option>
            </select>
          </div>

          <button
            onClick={handleCreateResearch}
            disabled={loading || !!jobId}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? '创建中...' : jobId ? '任务运行中...' : '开始研究'}
          </button>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}

          {jobId && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
              任务状态：{jobStatus || 'queued'} | Job ID: {jobId}
            </div>
          )}
        </div>
      </div>

      {/* Research History */}
      {researches.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            研究历史
          </h2>
          <div className="space-y-2">
            {researches.map((research) => (
              <div
                key={research.id}
                className={`p-3 rounded border cursor-pointer ${
                  currentResearch?.id === research.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
                onClick={() => setCurrentResearch(research)}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-medium">
                      主题：{research.themes.join(', ')}
                    </span>
                    <span className="ml-3 text-sm text-gray-500">
                      {new Date(research.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                      research.status
                    )}`}
                  >
                    {research.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Research Results */}
      {currentResearch && currentResearch.status === 'completed' && (
        <>
          {/* Overall Assessment */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              综合评估
            </h2>
            {currentResearch.overall_assessment && (
              <div className="mb-4">
                <span className="font-medium">结论：</span>
                <span
                  className={`ml-2 px-3 py-1 rounded text-sm font-medium ${
                    currentResearch.overall_assessment === 'recommended'
                      ? 'bg-green-100 text-green-800'
                      : currentResearch.overall_assessment === 'insufficient'
                      ? 'bg-yellow-100 text-yellow-800'
                      : currentResearch.overall_assessment === 'needs_review'
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {currentResearch.overall_assessment === 'recommended'
                    ? '建议继续研究'
                    : currentResearch.overall_assessment === 'insufficient'
                    ? '资料不足'
                    : currentResearch.overall_assessment === 'needs_review'
                    ? '待人工核实'
                    : '未发现主题证据'}
                </span>
              </div>
            )}
            {currentResearch.assessment_reasoning && (
              <p className="text-gray-700 mb-4">
                {currentResearch.assessment_reasoning}
              </p>
            )}
            {currentResearch.material_gaps &&
              currentResearch.material_gaps.length > 0 && (
                <div>
                  <span className="font-medium">资料缺口：</span>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {currentResearch.material_gaps.map((gap, idx) => (
                      <li key={idx} className="text-gray-700">
                        {gap}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
          </div>

          {/* Theme Matches */}
          {currentResearch.theme_matches &&
            currentResearch.theme_matches.length > 0 && (
              <div className="bg-white shadow rounded-lg p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  主题匹配结果
                </h2>
                <div className="space-y-4">
                  {currentResearch.theme_matches.map((match) => (
                    <div
                      key={match.id}
                      className="border border-gray-200 rounded-lg p-4"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium text-gray-900">
                          主题：{match.theme}
                        </h3>
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${getMatchStatusBadge(
                            match.status
                          )}`}
                        >
                          {match.status === 'candidate'
                            ? '候选匹配'
                            : match.status === 'pending'
                            ? '待核实'
                            : '未发现证据'}
                        </span>
                      </div>
                      <p className="text-gray-700 mb-3">{match.reasoning}</p>
                      {match.details?.suggested_themes?.length ? (
                        <p className="text-sm text-blue-700 mb-3">AI 建议的相关主题（待核实）：{match.details.suggested_themes.join('、')}</p>
                      ) : match.details ? <p className="text-sm text-gray-500 mb-3">暂未发现有资料支持的其他主题。</p> : null}
                      {match.details?.search_sources?.length ? (
                        <div className="text-sm text-gray-600 mb-3">
                          <span>本次主题搜索来源：</span>
                          <ul className="list-disc list-inside mt-1">
                            {match.details.search_sources.filter((source) => /^https?:\/\//i.test(source.url)).map((source, idx) => (
                              <li key={idx}><a className="text-blue-600 hover:underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title || source.url}</a></li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {match.evidence_quotes &&
                        match.evidence_quotes.length > 0 && (
                          <div className="bg-gray-50 rounded p-3">
                            <span className="text-sm font-medium text-gray-700">
                              证据引用：
                            </span>
                            <ul className="mt-2 space-y-1">
                              {match.evidence_quotes.map((quote, idx) => (
                                <li
                                  key={idx}
                                  className="text-sm text-gray-600 italic"
                                >
                                  "{quote}"
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              </div>
            )}

          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">综合书评</h2>
            <p className="text-sm text-gray-500 mb-4">AI 根据书评、图书馆资料和原文节选分章节撰写；节选不代表已读全文，引用前请核对原文。</p>
            <button onClick={generateArticle} disabled={articleLoading || reviewsLoading || (reviews.length === 0 && !currentResearch.sources?.some((source) => source.is_about_target_book && !source.is_duplicate && (source.summary || source.title.startsWith('Open Library 图书资料：') || source.title.startsWith('Project Gutenberg 原文节选：'))))} className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:bg-gray-400">{articleLoading ? '正在生成…' : article ? '查看已生成长篇书评' : '生成长篇综合书评'}</button>
            {!reviewsLoading && reviews.length === 0 && !currentResearch.sources?.some((source) => source.is_about_target_book && !source.is_duplicate && (source.summary || source.title.startsWith('Open Library 图书资料：') || source.title.startsWith('Project Gutenberg 原文节选：'))) && <p className="text-sm text-amber-700 mt-2">尚未收集到可用资料，请重新创建研究任务后再生成书评。</p>}
            {articleError && <p className="text-sm text-red-700 mt-3">{articleError}</p>}
            {article && <div className="mt-5 space-y-4">
              <h3 className="text-lg font-semibold">{article.title}</h3>
              {article.incomplete && <p className="text-sm text-amber-700">{article.warnings.join(' ')} 点击生成按钮可重试。</p>}
              <details className="text-sm text-gray-700 border rounded p-3"><summary className="cursor-pointer">资料初筛与证据精筛：{article.source_review.considered} 条中保留 {article.source_review.selected} 条</summary>
                {article.source_review.findings.map((item, index) => <p key={index} className="mt-2">{item.kind}：{item.text} <span className="text-blue-700">{item.source_ids.map((id) => `[${id}]`).join(' ')}</span></p>)}
                {article.source_review.gaps.map((gap, index) => <p key={index} className="mt-2 text-amber-700">资料缺口：{gap}</p>)}
              </details>
              {article.paragraphs.map((part, index) => <div key={index}>
                {(index === 0 || article.paragraphs[index - 1].section !== part.section) && <h4 className="font-semibold text-gray-900 mb-2">{part.section}</h4>}
                <p className="text-gray-700 leading-7 whitespace-pre-line">{part.text} <span className="text-blue-700 text-sm">{part.source_ids.map((id) => `[${id}]`).join(' ')}</span></p>
              </div>)}
              <div className="border-t pt-3 text-sm"><h4 className="font-medium mb-2">参考来源</h4><ul className="space-y-1">{article.sources.map((source) => <li key={source.source_id}>[{source.source_id}] {/^https?:\/\//i.test(source.url) ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{source.title}</a> : source.title}{source.basis === 'search_snippet' && '（依据搜索摘要）'}</li>)}</ul></div>
            </div>}
          </div>

          <PodcastPanel researchId={currentResearch.id} />

          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">书评整理</h2>
            <p className="text-sm text-gray-500 mb-4">AI 根据已收集资料整理各来源观点，请打开原文核实。</p>
            {reviewsLoading && <p className="text-sm text-gray-500">正在整理书评，首次可能需要一些时间…</p>}
            {reviewsError && <p className="text-sm text-red-700">部分书评整理失败或尚未完成。 <button className="underline" onClick={() => setReviewsAttempt(reviewsAttempt + 1)}>重试</button></p>}
            {!reviewsLoading && !reviewsError && reviews.length === 0 && <p className="text-sm text-gray-500">当前资料中没有可整理的书评。</p>}
            <div className="space-y-4">{reviews.map((review) => (
              <div key={review.source_id} className="border border-gray-200 rounded-lg p-4">
                <h3 className="font-medium text-gray-900">{review.title}</h3>
                <p className="text-xs text-gray-500 mt-1">{review.basis === 'page' ? '依据已获取网页文本（可能不完整）' : '依据搜索摘要，原网页未获取'}</p>
                <p className="text-sm text-gray-700 mt-3">{review.summary}</p>
                {review.points.length > 0 && <ul className="list-disc list-inside text-sm text-gray-700 mt-2">{review.points.map((point, index) => <li key={index}>{point}</li>)}</ul>}
                {/^https?:\/\//i.test(review.url) && <a className="text-sm text-blue-600 hover:underline" href={review.url} target="_blank" rel="noopener noreferrer">查看原文</a>}
              </div>
            ))}</div>
          </div>

          {/* Sources */}
          {currentResearch.sources && currentResearch.sources.length > 0 && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                来源资料（{currentResearch.sources.length}）
              </h2>
              <div className="space-y-4">
                {currentResearch.sources.map((source) => (
                  <div
                    key={source.id}
                    className="border border-gray-200 rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-medium text-gray-900 flex-1">
                        {source.title}
                      </h3>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ml-2 ${getSourceTypeBadge(
                          source.source_type
                        )}`}
                      >
                        {getSourceTypeLabel(source.source_type)}
                      </span>
                    </div>

                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline break-all"
                    >
                      {source.url}
                    </a>

                    {source.summary && (
                      <p className="text-sm text-gray-700 mt-3">
                        {source.summary}
                      </p>
                    )}

                    {source.key_points && source.key_points.length > 0 && (
                      <div className="mt-3">
                        <span className="text-sm font-medium text-gray-700">
                          关键观点：
                        </span>
                        <ul className="mt-1 space-y-1">
                          {source.key_points.map((point, idx) => (
                            <li
                              key={idx}
                              className="text-sm text-gray-600 list-disc list-inside"
                            >
                              {point}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {source.source_classification_reasoning && (
                      <p className="text-xs text-gray-500 mt-2">
                        分类理由：{source.source_classification_reasoning}
                      </p>
                    )}

                    <div className="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                      <span>
                        状态：
                        {source.fetch_status === 'fetched'
                          ? '已获取网页文本（可能不完整）'
                          : source.fetch_status === 'failed'
                          ? source.summary ? '原网页未获取，使用搜索摘要' : '原网页未获取，无可用摘要'
                          : source.fetch_status === 'parse_failed' ? '资料已获取，分类解析失败，需人工核对' : source.fetch_status}
                      </span>
                      {source.relevance_score !== null && (
                        <span>
                          相关性：{(source.relevance_score * 100).toFixed(0)}%
                        </span>
                      )}
                      {source.is_duplicate && (
                        <span className="text-orange-600">重复内容</span>
                      )}
                      {source.is_about_target_book === false && (
                        <span className="text-red-600">非目标书籍</span>
                      )}
                    </div>

                    {source.fetch_error && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                        {source.fetch_status === 'parse_failed' ? '分类解析失败，资料仍保留：' : '原网页未获取：'}{source.fetch_error}。
                        {source.fetch_status !== 'parse_failed' && (source.summary ? '已使用搜索摘要，内容需核实。' : '可尝试打开来源链接。')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Material Assessment */}
          {currentResearch.material_assessment && (
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                资料充分度详情
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    书籍身份确认：
                  </span>
                  <span className="ml-2">
                    {currentResearch.material_assessment
                      .book_identity_confirmed
                      ? '✓ 已确认'
                      : '✗ 未确认'}
                  </span>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    情节概要：
                  </span>
                  <span className="ml-2">
                    {currentResearch.material_assessment.has_plot_summary
                      ? '✓'
                      : '✗'}
                  </span>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    独立评论：
                  </span>
                  <span className="ml-2">
                    {currentResearch.material_assessment.has_independent_reviews
                      ? '✓'
                      : '✗'}
                  </span>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    作者背景：
                  </span>
                  <span className="ml-2">
                    {currentResearch.material_assessment.has_author_background
                      ? '✓'
                      : '✗'}
                  </span>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    多元视角：
                  </span>
                  <span className="ml-2">
                    {currentResearch.material_assessment
                      .has_multiple_perspectives
                      ? '✓'
                      : '✗'}
                  </span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-700">
                    专业书评：
                  </span>
                  <span className="ml-1">
                    {
                      currentResearch.material_assessment
                        .professional_review_count
                    }
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    独立评论：
                  </span>
                  <span className="ml-1">
                    {
                      currentResearch.material_assessment
                        .independent_review_count
                    }
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">
                    独立来源：
                  </span>
                  <span className="ml-1">
                    {currentResearch.material_assessment.total_unique_sources}
                  </span>
                </div>
              </div>

              {currentResearch.material_assessment.identified_gaps &&
                currentResearch.material_assessment.identified_gaps.length >
                  0 && (
                  <div className="mt-4">
                    <span className="text-sm font-medium text-gray-700">
                      识别的缺口：
                    </span>
                    <ul className="mt-2 space-y-1">
                      {currentResearch.material_assessment.identified_gaps.map(
                        (gap, idx) => (
                          <li
                            key={idx}
                            className="text-sm text-gray-600 list-disc list-inside"
                          >
                            {gap}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}

              {currentResearch.material_assessment.suggested_searches &&
                currentResearch.material_assessment.suggested_searches.length >
                  0 && (
                  <div className="mt-4">
                    <span className="text-sm font-medium text-gray-700">
                      建议补充搜索：
                    </span>
                    <ul className="mt-2 space-y-1">
                      {currentResearch.material_assessment.suggested_searches.map(
                        (search, idx) => (
                          <li
                            key={idx}
                            className="text-sm text-blue-600 list-disc list-inside"
                          >
                            {search}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}
            </div>
          )}
        </>
      )}

      {currentResearch && currentResearch.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-red-900 mb-2">
            研究任务失败
          </h2>
          <p className="text-red-700">{currentResearch.error_message}</p>
        </div>
      )}

      {currentResearch && currentResearch.status === 'running' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-blue-900 mb-2">
            研究进行中...
          </h2>
          <div className="flex items-center space-x-3">
            <div className="flex-1">
              <div className="w-full bg-blue-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{
                    width: `${(currentResearch.progress || 0) * 100}%`,
                  }}
                ></div>
              </div>
            </div>
            <span className="text-sm text-blue-700">
              {((currentResearch.progress || 0) * 100).toFixed(0)}%
            </span>
          </div>
          {currentResearch.current_step && (
            <p className="text-sm text-blue-700 mt-2">
              当前步骤：{currentResearch.current_step}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

