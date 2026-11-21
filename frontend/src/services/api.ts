import axios from 'axios'
import type {
  BookList,
  Book,
  Research,
  CreateResearchRequest,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Books API
export const booksApi = {
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
