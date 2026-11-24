import axios from 'axios'
import type {
  BookList,
  Book,
  Research,
  CreateResearchRequest,
} from '../types'

export type PodcastRun = {
  id: number; research_id: number; status: 'queued' | 'running' | 'completed' | 'needs_revision' | 'failed';
  speaker_count: number; speakers: string[]; language: 'zh' | 'en';
  current_step: string | null; error_message: string | null;
  audio_status: 'queued' | 'running' | 'completed' | 'failed' | null; audio_step: string | null; audio_error: string | null; audio_url: string | null; audio_voices: Record<string, string> | null;
  result: null | { plan: { premise: string; outline: Array<{ title: string; minutes: number; focus: string }> }; evidence: { gaps: string[] }; warnings: string[]; drafts: Array<{ iteration: number; content: string }>; reviews: Array<{ iteration: number; approved: boolean; issues: string[]; summary: string; estimated_minutes: number }>; sources: Array<{ source_id: number; title: string; url: string; source_type: string }> }
}

export type ThemeSearch = {
  id: number; theme: string; status: 'queued' | 'running' | 'completed' | 'failed';
  current_step: string | null; error_message: string | null;
  books: Array<{ id: number; title: string; author: string; isbn: string | null; catalog_url: string; reasoning: string; evidence_excerpt: string; evidence_url: string; author_country: string; author_evidence_excerpt: string; author_evidence_url: string }>;
}

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const healthApi = {
  checkQueue: async (queue: 'research' | 'podcast' | 'audio'): Promise<string | null> => {
    try {
      const response = await api.get('/health/deep', { timeout: 5000, validateStatus: () => true })
      const checks = response.data?.checks
      if (!checks) return '后端不可用，请检查 API 服务。'
      if (!checks.database?.ok) return '数据库不可用，请检查数据库服务。'
      if (!checks.redis?.ok) return '任务队列不可用，请检查 Redis。'
      if (checks.workers?.missing?.includes(queue)) return `任务队列不可用，请启动 ${queue} Worker。`
      return null
    } catch {
      return '后端不可用，请检查 API 服务。'
    }
  },
}

export type VoiceDefaults = { 主持人: string; 嘉宾: string }
export const configApi = {
  get: async (): Promise<{ default_voices: VoiceDefaults }> => (await api.get('/config')).data,
}

export const podcastApi = {
  create: async (data: { research_id: number; speaker_count: number; language: 'zh' | 'en'; theme: string; duration: number; style: string; audience: string; reference_text: string }): Promise<PodcastRun> => (await api.post('/podcasts/', data)).data,
  get: async (id: number): Promise<PodcastRun> => (await api.get(`/podcasts/${id}`)).data,
  retry: async (id: number): Promise<PodcastRun> => (await api.post(`/podcasts/${id}/retry`)).data,
  revise: async (id: number, reviewIteration: number, issueIndices: number[]): Promise<PodcastRun> => (await api.post(`/podcasts/${id}/revise`, { review_iteration: reviewIteration, issue_indices: issueIndices })).data,
  latest: async (researchId: number): Promise<PodcastRun | null> => (await api.get(`/podcasts/research/${researchId}`)).data,
  createAudio: async (id: number, voices: Record<string, string>, accept_review_issues: boolean): Promise<PodcastRun> => (await api.post(`/podcasts/${id}/audio`, { voices, accept_review_issues })).data,
  uploadVoice: async (sample: File, transcript: string, name: string): Promise<{ voice_id: string }> => {
    const form = new FormData()
    form.append('sample', sample)
    form.append('transcript', transcript)
    form.append('name', name)
    form.append('consent', 'true')
    return (await api.post('/podcasts/voices', form, { headers: { 'Content-Type': undefined }, timeout: 120000 })).data
  },
}

export const themeSearchApi = {
  create: async (theme: string, limit: number): Promise<ThemeSearch> => (await api.post('/theme-search/', { theme, limit })).data,
  get: async (id: number): Promise<ThemeSearch> => (await api.get(`/theme-search/${id}`)).data,
  latest: async (): Promise<ThemeSearch | null> => (await api.get('/theme-search/latest')).data,
}

// Books API
export const booksApi = {
  searchSingle: async (title: string, author = ''): Promise<{ books: Array<{ title: string; author: string; work_key: string | null; first_published: number | null; catalog_url: string | null; source: 'open_library' | 'web'; evidence_url?: string; evidence_excerpt?: string }>; references?: Array<{ title: string; url: string }> }> =>
    (await api.get('/books/search', { params: { title, author } })).data,
  addSingle: async (book: { title: string; author: string; work_key?: string }): Promise<Book> =>
    (await api.post('/books/single', book)).data,
  fetchAmazonList: async (listName: string, listUrl?: string): Promise<BookList> => {
    const response = await api.post('/books/lists/amazon', {
      list_name: listName,
      list_url: listUrl,
    })
    return response.data
  },

  uploadCSV: async (file: File, listName: string): Promise<BookList> => {
    const response = await api.post('/books/lists/csv', {
      csv_content: (await file.text()).replace(/^\uFEFF/, ''),
      list_name: listName,
    })
    return response.data
  },

  classifyTopics: async (listId: number): Promise<Record<string, string[]>> => {
    const response = await api.post(`/books/lists/${listId}/topics`)
    return response.data
  },

  getBookLists: async (): Promise<BookList[]> => {
    const response = await api.get('/books/lists')
    return response.data
  },

  getBookList: async (listId: number): Promise<BookList> => {
    const response = await api.get(`/books/lists/${listId}`)
    return response.data
  },

  getBook: async (bookId: number): Promise<Book> => {
    const response = await api.get(`/books/${bookId}`)
    return response.data
  },
}

// Research API
export const researchApi = {
  createResearch: async (data: CreateResearchRequest): Promise<{
    research_id: number
    job_id: string
    status: string
    message: string
  }> => {
    const response = await api.post('/research/', data)
    return response.data
  },

  createReviewArticle: async (researchId: number): Promise<{ title: string; incomplete: boolean; warnings: string[]; source_review: { considered: number; selected: number; findings: Array<{ kind: string; text: string; source_ids: number[] }>; gaps: string[] }; paragraphs: Array<{ text: string; source_ids: number[]; section: string }>; sources: Array<{ source_id: number; title: string; url: string; basis: 'page' | 'search_snippet' }> }> => {
    const response = await api.post(`/research/${researchId}/review-article`)
    return response.data
  },

  getReviewDigest: async (researchId: number): Promise<{ reviews: Array<{ source_id: number; title: string; url: string; basis: 'page' | 'search_snippet'; summary: string; points: string[] }>; incomplete: boolean }> => {
    const response = await api.get(`/research/${researchId}/reviews`)
    return response.data
  },

  getResearch: async (researchId: number): Promise<Research> => {
    const response = await api.get(`/research/${researchId}`)
    return response.data
  },

  getResearchForBook: async (bookId: number): Promise<Research[]> => {
    const response = await api.get(`/research/book/${bookId}`)
    return response.data
  },

  getJobStatus: async (jobId: string): Promise<{
    job_id: string
    status: string
    created_at: string | null
    started_at: string | null
    ended_at: string | null
    result: any
    exc_info: string | null
  }> => {
    const response = await api.get(`/research/job/${jobId}`)
    return response.data
  },
}

export default api
