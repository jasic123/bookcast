import { useEffect, useRef, useState } from 'react'
import { configApi, healthApi, podcastApi, voiceApi } from '../services/api'
import type { PodcastRun, VoiceDefaults, SavedVoice, PronunciationRule } from '../services/api'
import VoiceRecorder from './VoiceRecorder'

const voiceKey = (userId: number, role: string) => `podcast_voice_${userId}_${role}`
const presetVoice = (role: string, defaults: VoiceDefaults | null) =>
  role === '主持人' ? defaults?.['主持人'] || '' : ['嘉宾', '嘉宾1'].includes(role) ? defaults?.['嘉宾'] || '' : ''

export default function PodcastPanel({ researchId, userId }: { researchId: number; userId: number }) {
  const [theme, setTheme] = useState('')
  const [speakerCount, setSpeakerCount] = useState<number | null>(null)
  const [language, setLanguage] = useState<'zh' | 'en'>('zh')
  const [duration, setDuration] = useState(5)
  const [style, setStyle] = useState('自然口语')
  const [audience, setAudience] = useState('普通读者')
  const [reference, setReference] = useState('')
  const [voices, setVoices] = useState<Record<string, string>>({})
  const [defaultVoices, setDefaultVoices] = useState<VoiceDefaults | null>(null)
  const [savedVoices, setSavedVoices] = useState<SavedVoice[]>([])
  const [rules, setRules] = useState<PronunciationRule[]>([])
  const [originalWord, setOriginalWord] = useState('')
  const [spokenWord, setSpokenWord] = useState('')
  const [acceptReviewIssues, setAcceptReviewIssues] = useState(false)
  const [selectedIssues, setSelectedIssues] = useState<number[]>([])
  const [run, setRun] = useState<PodcastRun | null>(null)
  const [loading, setLoading] = useState(false)
  const creating = useRef(false)
  const audioCreating = useRef(false)
  const [audioSubmitting, setAudioSubmitting] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const refreshVoices = () => { voiceApi.list().then(items => { if (active) setSavedVoices(items) }).catch(() => {}) }
    refreshVoices()
    voiceApi.rules().then(items => { if (active) setRules(items) }).catch(() => {})
    window.addEventListener('focus', refreshVoices)
    return () => { active = false; window.removeEventListener('focus', refreshVoices) }
  }, [])

  useEffect(() => {
    let active = true
    const load = () => configApi.get().then(({ default_voices }) => {
      if (!active) return
      setDefaultVoices(default_voices)
    }).catch(() => { if (active) setError('无法获取默认音色，请检查后端服务。') })
    load()
    window.addEventListener('focus', load)
    return () => { active = false; window.removeEventListener('focus', load) }
  }, [])

  const updateVoice = (role: string, value: string) => {
    const key = voiceKey(userId, role)
    if (value && value !== presetVoice(role, defaultVoices)) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
    setVoices((previous) => ({ ...previous, [role]: value }))
  }

  useEffect(() => {
    let active = true
    setRun(null)
    setVoices({})
    setError(null)
    setAudioError(null)
    setAcceptReviewIssues(false)
    setSelectedIssues([])
    podcastApi.latest(researchId).then((result) => { if (active) setRun(result) }).catch(() => { if (active) setError('无法加载播客任务。') })
    return () => { active = false }
  }, [researchId])

  const activeSpeakers = run?.speakers?.length ? run.speakers : ['主持人', '嘉宾']
  const speakerKey = activeSpeakers.join('|')
  useEffect(() => {
    if (!run || !defaultVoices) return
    setVoices((previous) => {
      const next = { ...previous }
      for (const role of activeSpeakers) {
        if (!(role in next)) {
          const legacyKey = role === '主持人' ? 'podcast_host_voice' : role === '嘉宾' ? 'podcast_guest_voice' : `podcast_voice_${role}`
          const legacy = localStorage.getItem(legacyKey)
          if (legacy && legacy !== presetVoice(role, defaultVoices)) {
            voiceApi.restore(legacy).then(() => {
              localStorage.removeItem(legacyKey)
              voiceApi.list().then(setSavedVoices).catch(() => {})
            }).catch(() => {})
          }
          next[role] = localStorage.getItem(voiceKey(userId, role)) || presetVoice(role, defaultVoices)
        }
      }
      return next
    })
  }, [run?.id, speakerKey, defaultVoices, userId])

  useEffect(() => {
    if (!run || !(['queued', 'running'].includes(run.status) || ['queued', 'running'].includes(run.audio_status || ''))) return
    let active = true
    let timer: number
    const poll = async () => {
      try {
        const result = await podcastApi.get(run.id)
        if (active) setRun(result)
      } catch {
        // The health check below explains which dependency is unavailable.
      } finally {
        const issue = await healthApi.checkQueue(['queued', 'running'].includes(run.audio_status || '') ? 'audio' : 'podcast')
        if (active) setError(issue)
        if (active) timer = window.setTimeout(poll, 3000)
      }
    }
    timer = window.setTimeout(poll, 3000)
    return () => { active = false; window.clearTimeout(timer) }
  }, [run?.id, run?.status, run?.audio_status])

  const busy = loading || !!run && ['queued', 'running'].includes(run.status)
  const submit = async () => {
    if (creating.current) return
    if (!speakerCount) { setError('请先选择播客人数。'); return }
    creating.current = true
    setLoading(true)
    setError(null)
    setAcceptReviewIssues(false)
    setSelectedIssues([])
    try {
      setRun(await podcastApi.create({ research_id: researchId, speaker_count: speakerCount, language, theme: theme.trim(), duration, style, audience, reference_text: reference }))
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'object' ? `${detail.message}（任务 #${detail.run_id}）` : detail || '创建播客任务失败，请重试。')
      if (err.response?.status === 409) podcastApi.latest(researchId).then(setRun).catch(() => {})
    } finally { creating.current = false; setLoading(false) }
  }
  const createAudio = async () => {
    if (!run || audioCreating.current) return
    audioCreating.current = true
    setAudioSubmitting(true)
    setAudioError(null)
    const selectedVoices = Object.fromEntries(activeSpeakers.map((role) => [role, (voices[role] || '').trim()]))
    try { setRun(await podcastApi.createAudio(run.id, selectedVoices, acceptReviewIssues)) }
    catch (err: any) { setAudioError(typeof err.response?.data?.detail === 'string' ? err.response.data.detail : '创建配音任务失败，请重试。') }
    finally { audioCreating.current = false; setAudioSubmitting(false) }
  }
  const retry = async () => {
    if (!run || loading) return
    setLoading(true)
    setError(null)
    try { setRun(await podcastApi.retry(run.id)) }
    catch (err: any) { setError(err.response?.data?.detail?.message || err.response?.data?.detail || '续跑失败，请检查任务队列。') }
    finally { setLoading(false) }
  }
  const revise = async () => {
    const reviews = run?.result?.reviews
    const review = reviews?.[reviews.length - 1]
    if (!run || !review || !selectedIssues.length || loading) return
    setLoading(true)
    setError(null)
    try {
      setRun(await podcastApi.revise(run.id, review.iteration, selectedIssues))
      setSelectedIssues([])
      setAcceptReviewIssues(false)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'object' ? detail.message : detail || '按所选意见修改失败，请重试。')
    } finally { setLoading(false) }
  }

  const result = run?.result
  const lastDraft = result?.drafts?.[result.drafts.length - 1]
  const lastReview = result?.reviews?.[result.reviews.length - 1]
  return <div className="bg-white shadow rounded-lg p-6 mb-6">
    <h2 className="text-lg font-semibold text-gray-900">播客文稿</h2>
    <p className="text-sm text-gray-500 mt-2">选择人数后，由策划、资料研究、撰稿和评审 Agent 生成文稿；未通过时最多修改两轮。评审后可单独配音。</p>
    <div className="grid gap-3 md:grid-cols-2 mt-4">
      <label className="text-sm">播客人数（必选）<select value={speakerCount ?? ''} onChange={(e) => setSpeakerCount(e.target.value ? Number(e.target.value) : null)} className="mt-1 w-full rounded border px-3 py-2"><option value="">请选择人数</option><option value="1">单人讲述</option><option value="2">双人对谈</option><option value="3">三人圆桌</option><option value="4">四人圆桌</option></select></label>
      <label className="text-sm">文稿语言<select value={language} onChange={(e) => setLanguage(e.target.value as 'zh' | 'en')} className="mt-1 w-full rounded border px-3 py-2"><option value="zh">中文</option><option value="en">English</option></select></label>
      <label className="text-sm">播客主题（可留空）<input value={theme} onChange={(e) => setTheme(e.target.value)} maxLength={200} className="mt-1 w-full rounded border px-3 py-2" placeholder="例如：这本书如何描写友情" /></label>
      <label className="text-sm">目标时长（分钟）<input type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} min={2} max={20} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label className="text-sm">表达风格<select value={style} onChange={(e) => setStyle(e.target.value)} className="mt-1 w-full rounded border px-3 py-2"><option>自然口语</option><option>专业深入</option><option>轻松活泼</option></select></label>
      <label className="text-sm">目标听众<input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={100} className="mt-1 w-full rounded border px-3 py-2" /></label>
    </div>
    <label className="block text-sm mt-4">参考文章或笔记（可选，最多 2 万字）<textarea value={reference} onChange={(e) => setReference(e.target.value)} maxLength={20000} rows={3} className="mt-1 w-full rounded border px-3 py-2" placeholder="粘贴你有权使用的文字" /></label>
    <label className="block text-sm text-gray-600 mt-2">或导入 TXT / Markdown：<input type="file" accept=".txt,.md,text/plain,text/markdown" className="ml-2" onChange={async (event) => { const file = event.target.files?.[0]; if (!file) return; const text = await file.text(); if (text.length > 20000) { setError('参考文章超过 2 万字，请精简后再导入。'); return }; setReference(text); setError(null) }} /></label>
    <button onClick={submit} disabled={busy || !speakerCount || duration < 2 || duration > 20 || !Number.isInteger(duration)} className="mt-4 px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{busy ? '正在生成…' : '生成播客稿'}</button>
    {run && <p className="text-sm mt-3 text-gray-600">语言：{run.language === 'en' ? 'English' : '中文'} · 角色：{activeSpeakers.join('、')} · 任务状态：{run.current_step || (run.status === 'queued' ? '等待队列' : run.status)}</p>}
    {run?.status === 'needs_revision' && <p className="text-sm mt-2 text-amber-700">稿件已生成，但未通过事实与格式评审。请选择下方意见修改；确认问题后也可生成试听音频。</p>}
    {(error || run?.error_message) && <p className="text-sm mt-2 text-red-700">{error || run?.error_message}</p>}
    {run?.status === 'failed' && <button onClick={retry} disabled={loading} className="mt-3 px-4 py-2 rounded border border-blue-600 text-blue-700 disabled:opacity-50">{loading ? '正在续跑…' : '从最近检查点续跑'}</button>}
    {result && lastDraft && <div className="mt-5 space-y-4">
      <div className={lastReview?.approved ? 'text-green-700' : 'text-amber-700'}>{lastReview?.approved ? 'AI 评审通过，事实仍需人工核查' : '未通过评审，请根据意见人工修改'} · 共 {result.drafts.length} 版 · 预计 {lastReview?.estimated_minutes ?? '—'} 分钟</div>
      {!!result.warnings?.length && <p className="text-sm text-amber-700">{result.warnings.join(' ')}</p>}
      {lastReview?.issues?.length ? <div className="bg-amber-50 p-3 rounded text-sm"><strong>评审意见</strong><ul className="space-y-2 mt-2">{lastReview.issues.map((item, i) => <li key={i}>{run.status === 'needs_revision' ? <label className="flex items-start gap-2"><input type="checkbox" checked={selectedIssues.includes(i)} onChange={() => setSelectedIssues((previous) => previous.includes(i) ? previous.filter((index) => index !== i) : [...previous, i])} className="mt-1" /><span>{item}</span></label> : item}</li>)}</ul>{run.status === 'needs_revision' && <><button type="button" onClick={revise} disabled={loading || !selectedIssues.length} className="mt-3 px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{loading ? '正在提交修改…' : '按所选意见修改文稿'}</button><p className="text-gray-600 mt-2">保留当前版本，新稿会再次经过评审。</p></>}</div> : null}
      <details className="text-sm border rounded p-3"><summary className="cursor-pointer">策划大纲与证据缺口</summary><p className="mt-2">{result.plan?.premise}</p><ul className="list-disc ml-5 mt-2">{result.plan?.outline?.map((part, i) => <li key={i}>{part.title}（{part.minutes} 分钟）：{part.focus}</li>)}</ul>{result.evidence?.gaps?.map((gap, i) => <p className="text-amber-700 mt-1" key={i}>资料缺口：{gap}</p>)}</details>
      <div className="whitespace-pre-wrap text-gray-800 leading-7 border rounded p-4">{lastDraft.content}</div>
      {lastReview && <div className="border rounded p-4 space-y-3">
        <strong>分角色配音</strong>
        <p className="text-sm text-gray-500">每位角色单独设置音色；录制后的音色保存在账号中，下次可直接选择。配音会调用 SiliconFlow 语音接口。</p>
        {!lastReview.approved && <label className="flex items-start gap-2 text-sm text-amber-800"><input type="checkbox" checked={acceptReviewIssues} onChange={(e) => setAcceptReviewIssues(e.target.checked)} className="mt-1" /><span>这份文稿未通过 AI 评审。我已查看上方问题，仍要生成试听音频。</span></label>}
        <div className="grid gap-3 md:grid-cols-2">
          {activeSpeakers.map((role) => <label className="text-sm" key={role}>{role}音色<select value={voices[role] || ''} onChange={(e) => updateVoice(role, e.target.value)} className="mt-1 w-full rounded border px-3 py-2"><option value="">请选择音色</option>{defaultVoices && Object.entries(defaultVoices).map(([name, id]) => <option key={id} value={id}>预设：{name}</option>)}{savedVoices.filter(item => item.language === run.language).map(item => <option key={item.id} value={item.voice_id}>我的音色：{item.name}</option>)}</select></label>)}
        </div>
        <VoiceRecorder key={run.language} roles={activeSpeakers} language={run.language} onVoice={(role, id) => { updateVoice(role, id); voiceApi.list().then(setSavedVoices).catch(() => {}) }} />
        <div className="border rounded p-3 text-sm space-y-2"><strong>发音替换</strong><p className="text-gray-600">试听发现读错时，填写文稿原词和希望听到的读法。保存后重新配音；文稿文字不变。</p><div className="flex gap-2"><input aria-label="文稿原词" value={originalWord} onChange={e => setOriginalWord(e.target.value)} placeholder="例如 Cixin Liu" className="border rounded px-2 py-1" /><input aria-label="替代读法" value={spokenWord} onChange={e => setSpokenWord(e.target.value)} placeholder="例如 Tsee shin Lyoo" className="border rounded px-2 py-1" /><button className="bg-blue-600 text-white rounded px-3" onClick={async () => { try { await voiceApi.saveRule(originalWord, spokenWord); setRules(await voiceApi.rules()); setOriginalWord(''); setSpokenWord(''); setError(null) } catch (err: any) { setError(err.response?.data?.detail || '保存读法失败。') } }}>保存读法</button></div>{rules.map(item => <div key={item.id}>{item.original} → {item.spoken} <button className="text-red-700 underline" onClick={async () => { await voiceApi.removeRule(item.id); setRules(await voiceApi.rules()) }}>删除</button></div>)}</div>
        <button onClick={createAudio} disabled={audioSubmitting || !activeSpeakers.every((role) => voices[role]?.trim()) || (!lastReview.approved && !acceptReviewIssues) || ['queued', 'running'].includes(run.audio_status || '')} className="px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-400">{audioSubmitting ? '正在提交…' : ['queued', 'running'].includes(run.audio_status || '') ? '正在配音…' : lastReview.approved ? '生成播客音频' : '生成试听音频'}</button>
        {!activeSpeakers.every((role) => voices[role]?.trim()) && <p className="text-sm text-amber-700">请先为每位角色选择音色。</p>}
        {!lastReview.approved && !acceptReviewIssues && <p className="text-sm text-amber-700">请先勾选上方的评审问题确认框，或按评审意见修改文稿。</p>}
        {audioError && <p className="text-sm text-red-700">{audioError}</p>}
        {run.audio_step && <p className="text-sm text-gray-600">{run.audio_step}</p>}
        {run.audio_error && <p className="text-sm text-red-700">{run.audio_error}</p>}
        {run.audio_url && <><audio key={run.audio_url} controls src={run.audio_url} className="w-full" /><a href={run.audio_url} download className="text-sm text-blue-600 underline">下载 WAV 音频</a></>}
      </div>}
      {result.drafts.length > 1 && <details className="text-sm border rounded p-3"><summary className="cursor-pointer">查看之前的脚本版本</summary>{result.drafts.slice(0, -1).map((draft) => <div key={draft.iteration} className="mt-3"><strong>第 {draft.iteration} 版</strong><p className="whitespace-pre-wrap mt-2">{draft.content}</p></div>)}</details>}
      <details className="text-sm border rounded p-3"><summary className="cursor-pointer">查看资料来源和各版评审</summary><ul className="mt-2 space-y-1">{result.sources.map((source) => <li key={source.source_id}>[{source.source_id}] {/^https?:\/\//i.test(source.url) ? <a className="text-blue-600 underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a> : source.title}（{source.source_type}）</li>)}</ul>{result.reviews.map((review) => <p key={review.iteration} className="mt-2">第 {review.iteration} 版：{review.approved ? '通过' : '未通过'}；{review.summary} {review.issues.join('；')}</p>)}</details>
    </div>}
  </div>
}
