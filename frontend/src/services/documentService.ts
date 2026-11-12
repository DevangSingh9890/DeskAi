import axios from 'axios'
import { api } from './api'

export interface DocumentRecord {
  id: string
  filename: string
  size: number
  uploaded_at: string
}

export interface DocumentSummary {
  id: string
  filename: string
  size: number
  uploaded_at: string
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const { data } = await api.get<DocumentSummary[]>('/api/documents')
  return data
}

export async function uploadDocument(
  file: File,
  onProgress: (progress: number) => void,
): Promise<DocumentRecord> {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post<DocumentRecord>(
    '/api/documents/upload',
    formData,
    {
      onUploadProgress: (event) => {
        if (event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    },
  )
  return data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/api/documents/${encodeURIComponent(documentId)}`)
}

export function getDocumentErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    if (error.response?.data.detail) return error.response.data.detail
    if (error.code === 'ECONNABORTED') {
      return 'The request took too long. Please try again.'
    }
    if (!error.response) {
      return 'Could not connect to the service desk. Check that the backend is running and try again.'
    }
  }

  return 'Something went wrong. Please try again.'
}
