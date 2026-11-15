import axios from 'axios'
import { api } from './api'

export interface DocumentRecord {
  id: string
  filename: string
  size: number
  uploaded_at: string
  ingestion_status: IngestionStatus
  indexed_chunks: number
  processing_stage: IngestionStage | null
  processing_error: string | null
}

export interface DocumentSummary {
  id: string
  filename: string
  size: number
  uploaded_at: string
  ingestion_status: IngestionStatus
  indexed_chunks: number
  processing_stage: IngestionStage | null
  processing_error: string | null
}

export type IngestionStatus = 'Uploaded' | 'Processing' | 'Indexed' | 'Failed'
export type IngestionStage =
  | 'queued'
  | 'text_extraction'
  | 'chunking'
  | 'embedding_generation'
  | 'chroma_insert'
  | 'indexing'
export type DocumentJobStatus = 'uploaded' | 'processing' | 'completed' | 'failed'

export interface DocumentJobResponse {
  document_id: string
  status: DocumentJobStatus
  stage: IngestionStage | null
  error: string | null
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const { data } = await api.get<DocumentSummary[]>('/api/documents')
  return data
}

export async function uploadDocument(
  file: File,
  onProgress: (progress: number) => void,
): Promise<DocumentJobResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post<DocumentJobResponse>(
    '/api/documents/upload',
    formData,
    {
      timeout: 0, // File transfers may exceed the normal API request timeout.
      onUploadProgress: (event) => {
        if (event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    },
  )
  return data
}

export async function ingestDocument(documentId: string): Promise<DocumentJobResponse> {
  const { data } = await api.post<DocumentJobResponse>(
    `/api/knowledge-base/${encodeURIComponent(documentId)}/ingest`,
  )
  return data
}

export async function getDocumentStatus(
  documentId: string,
): Promise<DocumentJobResponse> {
  const { data } = await api.get<DocumentJobResponse>(
    `/api/documents/${encodeURIComponent(documentId)}/status`,
  )
  return data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/api/documents/${encodeURIComponent(documentId)}`)
}

export function getDocumentErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string | { stage?: string; error?: string } }>(error)) {
    const detail = error.response?.data.detail
    if (typeof detail === 'string') return detail
    if (detail?.error) {
      return detail.stage
        ? `Indexing failed at ${detail.stage}: ${detail.error}`
        : detail.error
    }
    if (error.code === 'ECONNABORTED') {
      return 'The request took too long. Please try again.'
    }
    if (!error.response) {
      return 'Could not connect to the service desk. Check that the backend is running and try again.'
    }
  }

  return 'Something went wrong. Please try again.'
}
