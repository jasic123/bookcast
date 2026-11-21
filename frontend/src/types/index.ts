// Book types
export interface Book {
  id: number
  book_list_id: number
  title: string
  author: string | null
  isbn: string | null
  asin: string | null
  rank: number | null
  description: string | null
  source_url: string | null
  platform_id: string | null
  created_at: string
}

export interface BookList {
  id: number
  name: string
  source_type: string
  source_url: string | null
  list_date: string | null
  fetched_at: string
  created_at: string
  books?: Book[]
}

// Research types
export type MatchStatus = 'candidate' | 'pending' | 'no_evidence'
export type SourceType =
  | 'professional_review'
  | 'reader_review'
  | 'publisher_description'
  | 'author_interview'
  | 'news_article'
  | 'encyclopedia'
  | 'other'
  | 'irrelevant'

export type SufficiencyLevel =
  | 'recommended'
  | 'insufficient'
  | 'needs_review'
  | 'no_theme_evidence'

export interface ThemeMatch {
  id: number
  research_id: number
  theme: string
  status: MatchStatus
  reasoning: string
  supporting_sources: number[] | null
  evidence_quotes: string[] | null
  details: { suggested_themes: string[]; search_sources: { title: string; url: string }[] } | null
  created_at: string
}

export interface Source {
  id: number
  research_id: number
  title: string
  url: string
  source_type: SourceType
  source_classification_reasoning: string | null
  raw_content: string | null
  cleaned_content: string | null
  summary: string | null
  key_points: string[] | null
  fetch_status: string
  fetch_error: string | null
  fetched_at: string | null
  is_duplicate: boolean
  duplicate_of: number | null
  relevance_score: number | null
  is_about_target_book: boolean
  book_identity_reasoning: string | null
  created_at: string
}

export interface MaterialAssessment {
  id: number
  research_id: number
  book_identity_confirmed: boolean
  book_identity_notes: string | null
  has_plot_summary: boolean
  has_independent_reviews: boolean
  has_author_background: boolean
  has_multiple_perspectives: boolean
  professional_review_count: number
  independent_review_count: number
  total_unique_sources: number
  source_diversity_score: number | null
  content_depth_score: number | null
  identified_gaps: string[] | null
  suggested_searches: string[] | null
  created_at: string
}

export interface Research {
  id: number
  book_id: number
  themes: string[]
  match_mode: string
  status: string
  progress: number
  current_step: string | null
  error_message: string | null
  overall_assessment: SufficiencyLevel | null
  assessment_reasoning: string | null
  material_gaps: string[] | null
  created_at: string
  completed_at: string | null
  book?: Book
  theme_matches?: ThemeMatch[]
  sources?: Source[]
  material_assessment?: MaterialAssessment
}

// API Request types
export interface FetchBooksRequest {
  source_type: 'amazon' | 'csv'
  list_name?: string
  list_url?: string
  csv_file?: File
}

export interface CreateResearchRequest {
  book_id: number
  themes: string[]
  match_mode?: 'any' | 'all'
}
