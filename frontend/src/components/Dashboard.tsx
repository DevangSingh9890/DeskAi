import { useCallback, useEffect, useState } from 'react'
import { ChatContainer } from './ChatContainer'
import { ChatInput } from './ChatInput'
import { SidebarKnowledgeBase } from './SidebarKnowledgeBase'
import {
  deleteDocument,
  getDocumentErrorMessage,
  getDocuments,
  uploadDocument,
} from '../services/documentService'
import type { DocumentSummary } from '../services/documentService'
import { getChatErrorMessage, sendChatMessage } from '../services/api'
import type { ChatMessage } from '../types/chat'

const greeting: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: "Hello, I'm your AI Service Desk Assistant. How can I help you today?",
  timestamp: new Date(),
}

export function Dashboard() {
  const [messages, setMessages] = useState<ChatMessage[]>([greeting])
  const [draft, setDraft] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadingFilename, setUploadingFilename] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const refreshDocuments = useCallback(async () => {
    const result = await getDocuments()
    setDocuments(result)
    setDocumentError(null)
  }, [])

  useEffect(() => {
    let active = true

    void Promise.resolve()
      .then(getDocuments)
      .then((result) => {
        if (active) {
          setDocuments(result)
          setDocumentError(null)
        }
      })
      .catch((error: unknown) => {
        if (active) setDocumentError(getDocumentErrorMessage(error))
      })
      .finally(() => {
        if (active) setIsDocumentsLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  async function handleSend() {
    const message = draft.trim()
    if (!message || isChatLoading) return

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      },
    ])
    setDraft('')
    setChatError(null)
    setIsChatLoading(true)

    try {
      const response = await sendChatMessage(message)
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response,
          timestamp: new Date(),
        },
      ])
    } catch (error: unknown) {
      setChatError(getChatErrorMessage(error))
    } finally {
      setIsChatLoading(false)
    }
  }

  async function handleUpload(file: File): Promise<boolean> {
    if (isUploading) return false

    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!extension || !['pdf', 'docx', 'txt'].includes(extension)) {
      setDocumentError('Only PDF, DOCX, and TXT files are supported.')
      return false
    }

    setDocumentError(null)
    setUploadingFilename(file.name)
    setUploadProgress(0)
    setIsUploading(true)
    try {
      await uploadDocument(file, setUploadProgress)
      try {
        await refreshDocuments()
      } catch (error: unknown) {
        setDocumentError(
          `Upload completed, but the document list could not be refreshed: ${getDocumentErrorMessage(error)}`,
        )
      }
      return true
    } catch (error: unknown) {
      setDocumentError(getDocumentErrorMessage(error))
      return false
    } finally {
      setIsUploading(false)
      setUploadingFilename(null)
    }
  }

  async function handleDelete(documentId: string) {
    if (deletingId) return

    setDocumentError(null)
    setDeletingId(documentId)
    try {
      await deleteDocument(documentId)
      setDocuments((currentDocuments) =>
        currentDocuments.filter((document) => document.id !== documentId),
      )
    } catch (error: unknown) {
      setDocumentError(getDocumentErrorMessage(error))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div className="dashboard-brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M16 3.5 19.1 12l8.4 4-8.4 3.1L16 28.5 12.9 19l-8.4-3 8.4-4L16 3.5Z" />
              <path d="m25.5 3 .9 2.6L29 6.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" />
            </svg>
          </span>
          <div className="dashboard-brand-copy">
            <h1>AI Service Desk Assistant</h1>
            <p>
              Upload support documentation, ask questions, and manage incidents
              from a single workspace.
            </p>
          </div>
        </div>
        <div className="dashboard-header-actions">
          <span className="header-status">
            <span className="status-dot" aria-hidden="true" />
            Service online
          </span>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-expanded={sidebarOpen}
            aria-label={sidebarOpen ? 'Collapse knowledge base panel' : 'Open knowledge base panel'}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M3 4.5h14v11H3zM8 4.5v11" />
            </svg>
            <span>Knowledge base</span>
          </button>
        </div>
      </header>

      {documentError && (
        <div className="dashboard-alert" role="alert">
          <span>{documentError}</span>
          <button type="button" onClick={() => setDocumentError(null)} aria-label="Dismiss error">
            ×
          </button>
        </div>
      )}

      <div
        className={`dashboard-workspace ${sidebarOpen ? 'dashboard-workspace--sidebar-open' : 'dashboard-workspace--sidebar-collapsed'}`}
      >
        <SidebarKnowledgeBase
          mobile
          documents={documents}
          isLoading={isDocumentsLoading}
          isUploading={isUploading}
          uploadProgress={uploadProgress}
          uploadingFilename={uploadingFilename}
          deletingId={deletingId}
          onUpload={handleUpload}
          onDelete={handleDelete}
          onClose={() => setSidebarOpen(false)}
        />
        <button
          className={`mobile-drawer-backdrop ${sidebarOpen ? 'mobile-drawer-backdrop--visible' : ''}`}
          type="button"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close knowledge base panel"
          tabIndex={sidebarOpen ? 0 : -1}
        />
        <main className="chat-workspace">
          <ChatContainer
            messages={messages}
            isLoading={isChatLoading}
            error={chatError}
            onSelectSuggestion={setDraft}
          />
          <ChatInput
            value={draft}
            isLoading={isChatLoading}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
            uploadingFilename={uploadingFilename}
            onChange={setDraft}
            onSubmit={handleSend}
            onAttach={(file) => void handleUpload(file)}
          />
          <p className="composer-privacy">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <rect x="3.5" y="7" width="9" height="7" rx="1.5" />
              <path d="M5.5 7V5a2 2 0 0 1 4 0v2" />
            </svg>
            Your conversation and documents stay within your workspace.
          </p>
        </main>
      </div>
    </div>
  )
}
