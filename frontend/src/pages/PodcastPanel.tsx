import { useEffect, useState } from 'react'
import { podcastApi } from '../services/api'
import type { PodcastRun } from '../services/api'

export default function PodcastPanel({ researchId }: { researchId: number }) {
  const [theme, setTheme] = useState('')
  const [duration, setDuration] = useState(5)
  const [style, setStyle] = useState('自然对谈')
  const [audience, setAudience] = useState('普通读者')
  const [reference, setReference] = useState('')
  const [hostVoice, setHostVoice] = useState('FunAudioLLM/CosyVoice2-0.5B:alex')
  const [guestVoice, setGuestVoice] = useState('FunAudioLLM/CosyVoice2-0.5B:anna')
  const [acceptReviewIssues, setAcceptReviewIssues] = useState(false)
  const [run, setRun] = useState<PodcastRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setRun(null)
    setError(null)
    setAcceptReviewIssues(false)
    podcastApi.latest(researchId).then((result) => { if (active) setRun(result) }).catch(() => { if (active) setError('无法加载播客任务。') })
    return () => { active = false }
  }, [researchId])

  useEffect(() => {
    if (!run || !(['queued', 'running'].includes(run.status) || ['queued', 'running'].includes(run.audio_status || ''))) return
    let active = true
    const timer = window.setInterval(() => {
      podcastApi.get(run.id).then((result) => { if (active) setRun(result) }).catch(() => { if (active) setError('获取播客任务进度失败，请刷新页面重试。') })
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [run?.id, run?.status, run?.audio_status])

  const busy = loading || !!run && ['queued', 'running'].includes(run.status)
  const submit = async () => {
    setLoading(true)
    setError(null)
    setAcceptReviewIssues(false)
    try {
      setRun(await podcastApi.create({ research_id: researchId, theme: theme.trim(), duration, style, audience, reference_text: reference }))
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建播客任务失败，请重试。')
    } finally { setLoading(false) }
  }
  const createAudio = async () => {
    if (!run) return
    setError(null)
    try { setRun(await podcastApi.createAudio(run.id, hostVoice.trim(), guestVoice.trim(), acceptReviewIssues)) }
    catch (err: any) { setError(err.response?.data?.detail || '创建配音任务失败，请重试。') }
  }

  const result = run?.result
  const lastDraft = result?.drafts?.[result.drafts.length - 1]
  const lastReview = result?.reviews?.[result.reviews.length - 1]
  return <div className="bg-white shadow rounded-lg p-6 mb-6">
    <h2 className="text-lg font-semibold text-gray-900">播客对话稿</h2>
    <p className="text-sm text-gray-500 mt-2">策划 → 搜索与证据筛选 → 主持人和嘉宾对话 → 评审；未通过时最多修改两轮。评审后可单独配音。</p>
    <div className="grid gap-3 md:grid-cols-2 mt-4">
      <label className="text-sm">播客主题（可留空）<input value={theme} onChange={(e) => setTheme(e.target.value)} maxLength={200} className="mt-1 w-full rounded border px-3 py-2" placeholder="例如：这本书如何描写友情" /></label>
      <label className="text-sm">目标时长（分钟）<input type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} min={2} max={20} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label className="text-sm">对话风格<select value={style} onChange={(e) => setStyle(e.target.value)} className="mt-1 w-full rounded border px-3 py-2"><option>自然对谈</option><option>专业深入</option><option>轻松活泼</option></select></label>
      <label className="text-sm">目标听众<input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={100} className="mt-1 w-full rounded border px-3 py-2" /></label>
    </div>
    <label className="block text-sm mt-4">参考文章或笔记（可选，最多 2 万字）<textarea value={reference} onChange={(e) => setReference(e.target.value)} maxLength={20000} rows={3} className="mt-1 w-full rounded border px-3 py-2" placeholder="粘贴你有权使用的文字" /></label>
    <label className="block text-sm text-gray-600 mt-2">或导入 TXT / Markdown：<input type="file" accept=".txt,.md,text/plain,text/markdown" className="ml-2" onChange={async (event) => { const file = event.target.files?.[0]; if (!file) return; const text = await file.text(); if (text.length > 20000) { setError('参考文章超过 2 万字，请精简后再导入。'); return }; setReference(text); setError(null) }} /></label>
    <button onClick={submit} disabled={busy || duration < 2 || duration > 20 || !Number.isInteger(duration)} className="mt-4 px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{busy ? '正在生成…' : '生成播客对话稿'}</button>
    {run && <p className="text-sm mt-3 text-gray-600">任务状态：{run.current_step || (run.status === 'queued' ? '等待队列' : run.status)}</p>}
    {(error || run?.error_message) && <p className="text-sm mt-2 text-red-700">{error || run?.error_message}</p>}
    {result && lastDraft && <div className="mt-5 space-y-4">
      <div className={lastReview?.approved ? 'text-green-700' : 'text-amber-700'}>{lastReview?.approved ? 'AI 评审通过，事实仍需人工核查' : '未通过评审，请根据意见人工修改'} · 共 {result.drafts.length} 版 · 预计 {lastReview?.estimated_minutes ?? '—'} 分钟</div>
      {!!result.warnings?.length && <p className="text-sm text-amber-700">{result.warnings.join(' ')}</p>}
      {lastReview?.issues?.length ? <div className="bg-amber-50 p-3 rounded text-sm"><strong>评审意见</strong><ul className="list-disc ml-5 mt-1">{lastReview.issues.map((item, i) => <li key={i}>{item}</li>)}</ul></div> : null}
      <details className="text-sm border rounded p-3"><summary className="cursor-pointer">策划大纲与证据缺口</summary><p className="mt-2">{result.plan?.premise}</p><ul className="list-disc ml-5 mt-2">{result.plan?.outline?.map((part, i) => <li key={i}>{part.title}（{part.minutes} 分钟）：{part.focus}</li>)}</ul>{result.evidence?.gaps?.map((gap, i) => <p className="text-amber-700 mt-1" key={i}>资料缺口：{gap}</p>)}</details>
      <div className="whitespace-pre-wrap text-gray-800 leading-7 border rounded p-4">{lastDraft.content}</div>
      {lastReview && <div className="border rounded p-4 space-y-3">
        <strong>分角色配音</strong>
        <p className="text-sm text-gray-500">默认使用预设音色；以后获得个人定制音色 ID，可填入对应角色。配音会调用 SiliconFlow 语音接口。</p>
        {!lastReview.approved && <label className="flex items-start gap-2 text-sm text-amber-800"><input type="checkbox" checked={acceptReviewIssues} onChange={(e) => setAcceptReviewIssues(e.target.checked)} className="mt-1" /><span>这份文稿未通过 AI 评审。我已查看上方问题，仍要生成试听音频。</span></label>}
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">主持人音色 ID<input value={hostVoice} onChange={(e) => setHostVoice(e.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label>
          <label className="text-sm">嘉宾音色 ID<input value={guestVoice} onChange={(e) => setGuestVoice(e.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label>
        </div>
        <button onClick={createAudio} disabled={!hostVoice.trim() || !guestVoice.trim() || (!lastReview.approved && !acceptReviewIssues) || ['queued', 'running'].includes(run.audio_status || '')} className="px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{['queued', 'running'].includes(run.audio_status || '') ? '正在配音…' : lastReview.approved ? '生成播客音频' : '生成试听音频'}</button>
        {run.audio_step && <p className="text-sm text-gray-600">{run.audio_step}</p>}
        {run.audio_error && <p className="text-sm text-red-700">{run.audio_error}</p>}
        {run.audio_url && <><audio controls src={run.audio_url} className="w-full" /><a href={run.audio_url} download className="text-sm text-blue-600 underline">下载 WAV 音频</a></>}
      </div>}
      {result.drafts.length > 1 && <details className="text-sm border rounded p-3"><summary className="cursor-pointer">查看之前的脚本版本</summary>{result.drafts.slice(0, -1).map((draft) => <div key={draft.iteration} className="mt-3"><strong>第 {draft.iteration} 版</strong><p className="whitespace-pre-wrap mt-2">{draft.content}</p></div>)}</details>}
      <details className="text-sm border rounded p-3"><summary className="cursor-pointer">查看资料来源和各版评审</summary><ul className="mt-2 space-y-1">{result.sources.map((source) => <li key={source.source_id}>[{source.source_id}] {/^https?:\/\//i.test(source.url) ? <a className="text-blue-600 underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a> : source.title}（{source.source_type}）</li>)}</ul>{result.reviews.map((review) => <p key={review.iteration} className="mt-2">第 {review.iteration} 版：{review.approved ? '通过' : '未通过'}；{review.summary} {review.issues.join('；')}</p>)}</details>
    </div>}
  </div>
}
