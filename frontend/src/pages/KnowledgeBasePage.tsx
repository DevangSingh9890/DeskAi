import { useCallback, useEffect, useState } from 'react'

import { SidebarKnowledgeBase } from '../components/SidebarKnowledgeBase'
import {
  deleteDocument,
  getDocumentErrorMessage,
  getDocuments,
  getDocumentStatus,
  uploadDocument,
} from '../services/documentService'
import type {
  DocumentJobStatus,
  DocumentSummary,
  IngestionStatus,
} from '../services/documentService'
import type { PerformanceStatus } from '../services/api'

interface KnowledgeBasePageProps {
  performanceStatus: PerformanceStatus | null
}

const ingestionStatusByJobStatus: Record<DocumentJobStatus, IngestionStatus> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  completed: 'Indexed',
  failed: 'Failed',
}

export function KnowledgeBasePage({ performanceStatus }: KnowledgeBasePageProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadingFilename, setUploadingFilename] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const isIndexing = documents.some(
    (document) =>
      document.ingestion_status === 'Processing' &&
      !(
        document.processing_stage === 'queued' &&
        performanceStatus?.warmup_status !== 'completed'
      ),
  )
  const indexedDocumentCount = documents.filter(
    (document) => document.ingestion_status === 'Indexed',
  ).length
  const totalChunks = documents.reduce(
    (total, document) => total + document.indexed_chunks,
    0,
  )
  const knowledgeHealth = documents.some(
    (document) => document.ingestion_status === 'Failed',
  )
    ? 'Needs attention'
    : isIndexing
      ? 'Indexing'
      : documents.some((document) => document.ingestion_status !== 'Indexed')
        ? 'Action needed'
        : performanceStatus?.embedding_model_loaded
          ? 'Healthy'
          : 'Warming up'
  const processingDocumentIds = documents
    .filter((document) => document.ingestion_status === 'Processing')
    .map((document) => document.id)
    .sort()
    .join(',')
  const indexingDocument = documents.find(
    (document) => document.ingestion_status === 'Processing',
  )
  const activeDocumentFilename = isUploading
    ? uploadingFilename
    : indexingDocument?.filename ?? null

  const refreshDocuments = useCallback(async () => {
    const result = await getDocuments()
    setDocuments(result)
    setError(null)
  }, [])

  useEffect(() => {
    let active = true

    void Promise.resolve()
      .then(getDocuments)
      .then((result) => {
        if (active) {
          setDocuments(result)
          setError(null)
        }
      })
      .catch((loadError: unknown) => {
        if (active) setError(getDocumentErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!processingDocumentIds) return

    const documentIds = processingDocumentIds.split(',')
    let active = true
    let timeoutId: number | undefined

    async function pollDocumentStatuses() {
      try {
        const statuses = await Promise.all(
          documentIds.map(async (documentId) => [
            documentId,
            await getDocumentStatus(documentId),
          ] as const),
        )
        if (!active) return

        const statusesById = new Map(statuses)
        setDocuments((currentDocuments) =>
          currentDocuments.map((document) => {
            const job = statusesById.get(document.id)
            if (!job) return document
            return {
              ...document,
              ingestion_status: ingestionStatusByJobStatus[job.status],
              processing_stage: job.stage,
              processing_error: job.error,
            }
          }),
        )
      } catch (pollError: unknown) {
        if (active) setError(getDocumentErrorMessage(pollError))
      } finally {
        if (active) {
          timeoutId = window.setTimeout(() => {
            void pollDocumentStatuses()
          }, 1500)
        }
      }
    }

    timeoutId = window.setTimeout(() => {
      void pollDocumentStatuses()
    }, 1000)

    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [processingDocumentIds])

  async function handleUpload(file: File): Promise<boolean> {
    if (isUploading || isIndexing) return false

    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!extension || !['pdf', 'docx', 'txt'].includes(extension)) {
      setError('Only PDF, DOCX, and TXT files are supported.')
      return false
    }

    setError(null)
    setNotice(null)
    setUploadingFilename(file.name)
    setUploadProgress(0)
    setIsUploading(true)
    try {
      const uploaded = await uploadDocument(file, setUploadProgress)
      if (uploaded.status === 'warming') {
        setNotice(
          uploaded.message ??
            'Embedding model is still warming up. Please wait.',
        )
        try {
          await refreshDocuments()
        } catch (refreshError: unknown) {
          setError(
            `The uploaded document status could not be refreshed: ${getDocumentErrorMessage(refreshError)}`,
          )
        }
        return true
      }

      setDocuments((currentDocuments) => [
        {
          id: uploaded.document_id,
          filename: file.name,
          size: file.size,
          uploaded_at: new Date().toISOString(),
          ingestion_status: ingestionStatusByJobStatus[uploaded.status],
          indexed_chunks: 0,
          processing_stage: uploaded.stage,
          processing_error: uploaded.error,
        },
        ...currentDocuments.filter(
          (document) => document.id !== uploaded.document_id,
        ),
      ])
      try {
        await refreshDocuments()
      } catch (refreshError: unknown) {
        setError(
          `The uploaded document status could not be refreshed: ${getDocumentErrorMessage(refreshError)}`,
        )
      }
      if (uploaded.status === 'failed') {
        const stage = uploaded.stage ? ` at ${uploaded.stage}` : ''
        setError(
          `Indexing failed${stage}: ${uploaded.error ?? 'Check backend logs.'}`,
        )
      }
      return true
    } catch (uploadError: unknown) {
      setError(getDocumentErrorMessage(uploadError))
      return false
    } finally {
      setIsUploading(false)
      setUploadingFilename(null)
    }
  }

  async function handleDelete(documentId: string) {
    if (deletingId) return

    setError(null)
    setDeletingId(documentId)
    try {
      await deleteDocument(documentId)
      setDocuments((currentDocuments) =>
        currentDocuments.filter((document) => document.id !== documentId),
      )
    } catch (deleteError: unknown) {
      setError(getDocumentErrorMessage(deleteError))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="ticket-page-shell knowledge-base-shell">
      <div className="knowledge-base-page">
        <header className="knowledge-base-page-header">
          <div>
            <p className="ticket-eyebrow">ADMINISTRATION</p>
            <h2>Knowledge Base</h2>
            <p>Manage the documents used to ground AI support answers.</p>
          </div>
          <span className="knowledge-base-page-rag-status" role="status">
            RAG Status: {performanceStatus?.embedding_model_loaded
              ? 'Ready'
              : performanceStatus?.warmup_status === 'failed'
                ? 'Unavailable'
                : performanceStatus?.warming
                  ? 'Warming up'
                  : 'Checking'}
          </span>
        </header>

        {error && (
          <div className="dashboard-alert" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}
        {notice && (
          <div className="dashboard-notice" role="status" aria-live="polite">
            {notice}
          </div>
        )}

        <div className="knowledge-stat-grid" aria-label="Knowledge base statistics">
          <article className="knowledge-stat-card">
            <span className="knowledge-stat-icon knowledge-stat-icon--violet">▧</span>
            <div><p>Total documents</p><strong>{documents.length}</strong></div>
            <small>in your library</small>
          </article>
          <article className="knowledge-stat-card">
            <span className="knowledge-stat-icon knowledge-stat-icon--green">✓</span>
            <div><p>Indexed documents</p><strong>{indexedDocumentCount}</strong></div>
            <small>ready for AI search</small>
          </article>
          <article className="knowledge-stat-card">
            <span className="knowledge-stat-icon knowledge-stat-icon--blue">▤</span>
            <div><p>Total chunks</p><strong>{totalChunks.toLocaleString()}</strong></div>
            <small>knowledge segments</small>
          </article>
          <article className="knowledge-stat-card">
            <span className="knowledge-stat-icon knowledge-stat-icon--amber">✦</span>
            <div><p>Knowledge health</p><strong className="knowledge-health-value">{knowledgeHealth}</strong></div>
            <small>RAG engine {performanceStatus?.embedding_model_loaded ? 'connected' : 'warming up'}</small>
          </article>
        </div>

        <SidebarKnowledgeBase
          documents={documents}
          isLoading={isLoading}
          isUploading={isUploading}
          isIndexing={isIndexing}
          uploadProgress={uploadProgress}
          uploadingFilename={activeDocumentFilename}
          deletingId={deletingId}
          onUpload={handleUpload}
          onDelete={(documentId) => void handleDelete(documentId)}
        />
      </div>
    </section>
  )
}
