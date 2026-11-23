import { useEffect, useRef, useState } from 'react'
import { podcastApi } from '../services/api'

const SAMPLE_TEXT = '今天想聊一本特别的书。它为什么让人念念不忘？我们一起看看。'

async function toWav(blob: Blob): Promise<File> {
  const context = new AudioContext()
  let audio: AudioBuffer
  try { audio = await context.decodeAudioData(await blob.arrayBuffer()) }
  finally { await context.close() }
  if (audio.duration < 6) throw new Error('录音不足 6 秒，请自然朗读完整示例文字。')
  const samples = audio.getChannelData(0)
  const bytes = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(bytes)
  const label = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)) }
  label(0, 'RIFF'); view.setUint32(4, bytes.byteLength - 8, true); label(8, 'WAVE'); label(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, audio.sampleRate, true); view.setUint32(28, audio.sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); label(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  samples.forEach((sample, i) => view.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, sample)) * 32767), true))
  return new File([bytes], 'voice-sample.wav', { type: 'audio/wav' })
}

export default function VoiceRecorder({ roles, onVoice }: { roles: string[]; onVoice: (role: string, voiceId: string) => void }) {
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<number | null>(null)
  const [recording, setRecording] = useState(false)
  const [sample, setSample] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [transcript, setTranscript] = useState(SAMPLE_TEXT)
  const [name, setName] = useState('my_voice')
  const [role, setRole] = useState(roles[0] || '主持人')
  const [consent, setConsent] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [voiceId, setVoiceId] = useState('')
  const rolesKey = roles.join('|')

  useEffect(() => { if (!roles.includes(role)) setRole(roles[0] || '主持人') }, [rolesKey, role])
  useEffect(() => {
    return () => { if (recorder.current?.state === 'recording') recorder.current.stop(); stream.current?.getTracks().forEach((track) => track.stop()); if (timer.current) window.clearTimeout(timer.current) }
  }, [])
  useEffect(() => {
    if (!sample) { setPreview(''); return }
    const url = URL.createObjectURL(sample)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [sample])

  const start = async () => {
    setError(''); setVoiceId(''); setSample(null)
    try {
      const microphone = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } })
      stream.current = microphone
      const capture = new MediaRecorder(microphone)
      recorder.current = capture
      const chunks: Blob[] = []
      capture.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
      capture.onstop = async () => {
        microphone.getTracks().forEach((track) => track.stop())
        setRecording(false)
        try { setSample(await toWav(new Blob(chunks, { type: capture.mimeType }))) }
        catch (err) { setError(err instanceof Error ? err.message : '录音无法转换为 WAV，请上传 WAV 或 MP3 文件。') }
      }
      capture.start()
      setRecording(true)
      timer.current = window.setTimeout(() => capture.stop(), 10000)
    } catch { setError('无法使用麦克风；请检查浏览器权限，或直接上传录音。') }
  }
  const stop = () => { if (timer.current) window.clearTimeout(timer.current); if (recorder.current?.state === 'recording') recorder.current.stop() }
  const upload = async () => {
    if (!sample || !consent) return
    setUploading(true); setError('')
    try {
      const result = await podcastApi.uploadVoice(sample, transcript.trim(), name.trim())
      setVoiceId(result.voice_id)
      onVoice(role, result.voice_id)
    } catch (err: any) { setError(err.response?.data?.detail || '音色创建失败，请检查录音格式和语音服务配置。') }
    finally { setUploading(false) }
  }

  return <div className="border rounded p-4 space-y-3 text-sm">
    <strong>录制个人音色</strong>
    <p className="text-gray-600">在安静房间用正常语速、自然语调完整朗读下面的文字，约 8–10 秒；不要赶在截止前读完。先试听，若有杂音、回声或句尾被截断，请重录。上传文件时，录音对应文字必须与实际读出的内容一致。服务商要求账号完成实名认证。</p>
    <p className="bg-gray-50 rounded p-2">{SAMPLE_TEXT}</p>
    <div className="flex gap-2"><button type="button" onClick={recording ? stop : start} className="rounded bg-gray-800 text-white px-3 py-1">{recording ? '停止录音' : '开始录音（最多 10 秒）'}</button>
      <input type="file" accept=".wav,.mp3,audio/wav,audio/mpeg" onChange={(event) => { setSample(event.target.files?.[0] || null); setVoiceId('') }} /></div>
    {preview && <audio controls src={preview} className="w-full" />}
    <label className="block">录音对应文字<input value={transcript} onChange={(event) => setTranscript(event.target.value)} maxLength={500} className="mt-1 w-full rounded border px-2 py-1" /></label>
    <label className="block">音色名称（英文、数字、_、-）<input value={name} onChange={(event) => setName(event.target.value)} maxLength={30} className="mt-1 w-full rounded border px-2 py-1" /></label>
    <label className="block">用于角色<select value={role} onChange={(event) => setRole(event.target.value)} className="mt-1 rounded border px-2 py-1">{roles.map((item) => <option key={item}>{item}</option>)}</select></label>
    <label className="flex gap-2 items-start"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1" />我确认录音属于本人或已获声音所有者授权，并同意上传到语音服务创建音色。</label>
    <button type="button" onClick={upload} disabled={!sample || !consent || !transcript.trim() || !name.trim() || uploading} className="rounded bg-blue-600 text-white px-3 py-1 disabled:bg-gray-400">{uploading ? '正在创建音色…' : '创建音色并用于' + role}</button>
    {voiceId && <p className="text-green-700">音色已创建，已填入{role}音色 ID：{voiceId}</p>}
    {error && <p className="text-red-700">{error}</p>}
  </div>
}
