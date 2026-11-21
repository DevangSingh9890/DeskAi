import { useCallback, useEffect, useState } from 'react'
import { ChatContainer } from './ChatContainer'
import { ChatInput } from './ChatInput'
import { SidebarKnowledgeBase } from './SidebarKnowledgeBase'
import { TicketsDashboard } from '../pages/TicketsDashboard'
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
import {
  getChatErrorMessage,
  getPerformanceStatus,
  sendAgentChatMessage,
} from '../services/api'
import type { PerformanceStatus } from '../services/api'
import type { ChatMessage } from '../types/chat'
import type { TicketCreateRequest, TicketPriority } from '../types/ticket'
import {
  approveTicket,
  getTicketErrorMessage,
} from '../services/ticketService'
import {
  createHandoff,
  getHandoffErrorMessage,
  getHumanConversation,
  isHandoffNotFound,
} from '../services/handoffService'
import type { CreateHandoffRequest } from '../types/handoff'
import { HumanChatWidget } from './HumanChatWidget'
import { HumanSupportPopup } from './HumanSupportPopup'
import '../human-support.css'

const greeting: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: "Hello, I'm your AI Service Desk Assistant. How can I help you today?",
  timestamp: new Date(),
}

const ingestionStatusByJobStatus: Record<DocumentJobStatus, IngestionStatus> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  completed: 'Indexed',
  failed: 'Failed',
}

function isTicketPriority(value: string | null | undefined): value is TicketPriority {
  return (
    value === 'Critical' ||
    value === 'High' ||
    value === 'Medium' ||
    value === 'Low'
  )
}

function getTicketDetails(message: ChatMessage): TicketCreateRequest | undefined {
  const classification = message.agentResponse?.classification
  const description = message.originalUserMessage ?? message.content
  if (
    !classification?.issue ||
    !classification.category ||
    !classification.subcategory ||
    !classification.assigned_group ||
    !isTicketPriority(classification.priority)
  ) {
    return undefined
  }

  return {
    title: classification.issue,
    description,
    priority: classification.priority,
    category: classification.category,
    subcategory: classification.subcategory,
    assigned_group: classification.assigned_group,
    created_by: 'user',
    impact: classification.impact ?? undefined,
    ai_recommendation:
      message.agentResponse?.ticket_recommendation?.reason ?? undefined,
    knowledge_sources: message.agentResponse?.knowledge_sources ?? [],
    similar_incidents: message.agentResponse?.similar_tickets ?? [],
  }
}

export function Dashboard() {
  const [activeView, setActiveView] = useState<'chat' | 'tickets'>('chat')
  const [handoffConversationId, setHandoffConversationId] = useState<string | null>(null)
  const [showHandoffPopup, setShowHandoffPopup] = useState(false)
  const [isHandoffPending, setIsHandoffPending] = useState(false)
  const [handoffError, setHandoffError] = useState<string | null>(null)
  const [ticketsRefreshKey, setTicketsRefreshKey] = useState(0)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting])
  const [draft, setDraft] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [agentProgress, setAgentProgress] = useState<number | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [performanceStatus, setPerformanceStatus] =
    useState<PerformanceStatus | null>(null)
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadingFilename, setUploadingFilename] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [documentNotice, setDocumentNotice] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  useEffect(() => {
    let active = true
    let timeoutId: number | undefined
    const storedConversationId = window.localStorage.getItem(
      'deskai-human-support-conversation',
    )
    if (!storedConversationId) return
    const savedConversationId = storedConversationId

    function clearStoredConversation() {
      if (
        window.localStorage.getItem('deskai-human-support-conversation') ===
        savedConversationId
      ) {
        window.localStorage.removeItem('deskai-human-support-conversation')
      }
    }

    async function restoreActiveConversation() {
      try {
        const detail = await getHumanConversation(savedConversationId)
        if (!active) return
        if (
          detail.conversation.status === 'Resolved' ||
          detail.conversation.status === 'Closed'
        ) {
          clearStoredConversation()
          return
        }
        setHandoffConversationId(savedConversationId)
      } catch (error: unknown) {
        if (!active) return
        if (isHandoffNotFound(error)) {
          clearStoredConversation()
          return
        }
        timeoutId = window.setTimeout(
          () => void restoreActiveConversation(),
          2000,
        )
      }
    }

    void restoreActiveConversation()
    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [])
  const isIndexing = documents.some(
    (document) =>
      document.ingestion_status === 'Processing' &&
      !(
        document.processing_stage === 'queued' &&
        performanceStatus?.warmup_status !== 'ready'
      ),
  )
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

  useEffect(() => {
    let active = true
    let timeoutId: number | undefined

    async function pollPerformanceStatus() {
      try {
        const status = await getPerformanceStatus()
        if (!active) return
        setPerformanceStatus(status)
        if (status.warming || status.warmup_status === 'not_started') {
          timeoutId = window.setTimeout(
            () => void pollPerformanceStatus(),
            1000,
          )
        }
      } catch {
        if (active) {
          timeoutId = window.setTimeout(
            () => void pollPerformanceStatus(),
            3000,
          )
        }
      }
    }

    void pollPerformanceStatus()
    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
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
      } catch (error: unknown) {
        if (active) setDocumentError(getDocumentErrorMessage(error))
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
    setAgentProgress(0)
    const startedAt = performance.now()
    const progressTimer = window.setInterval(() => {
      setAgentProgress((currentStep) =>
        currentStep === null ? 0 : Math.min(currentStep + 1, 3),
      )
    }, 2200)

    try {
      const result = await sendAgentChatMessage(message)
      const completedAt = new Date()
      const needsHumanSupport =
        !(result.knowledge_results?.length || result.knowledge_sources?.length) ||
        /could not find|no useful answer|unable to help/i.test(result.response ?? '') ||
        /\b(human|real person|support engineer|representative|live agent)\b/i.test(message)
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: result.response ?? '',
          agentResponse: result,
          workflowDurationMs: performance.now() - startedAt,
          originalUserMessage: message,
          timestamp: completedAt,
          handoffRecommended: needsHumanSupport,
        },
      ])
    } catch (error: unknown) {
      setChatError(getChatErrorMessage(error))
    } finally {
      window.clearInterval(progressTimer)
      setAgentProgress(null)
      setIsChatLoading(false)
    }
  }

  async function handleHandoff(messageId: string) {
    if (isHandoffPending || handoffConversationId) return
    const sourceMessage = messages.find((message) => message.id === messageId)
    if (!sourceMessage?.agentResponse) return

    setIsHandoffPending(true)
    setHandoffError(null)
    const conversationMessages: CreateHandoffRequest['messages'] = messages.map(
      (message) => ({
        role: message.role,
        content: message.content,
        timestamp: message.timestamp.toISOString(),
        metadata: {
          ...(message.agentResponse ? { agent_response: message.agentResponse } : {}),
          ...(message.classification ? { classification: message.classification } : {}),
          ...(message.originalUserMessage
            ? { original_user_message: message.originalUserMessage }
            : {}),
          ...(message.createdTicket ? { ticket_data: message.createdTicket } : {}),
        },
      }),
    )
    const classification = sourceMessage.agentResponse.classification
    const ticketData =
      sourceMessage.createdTicket ?? getTicketDetails(sourceMessage) ?? null
    const payload: CreateHandoffRequest = {
      messages: conversationMessages,
      context: {
        classification: classification ?? null,
        knowledge_sources: sourceMessage.agentResponse.knowledge_sources ?? [],
        knowledge_results: sourceMessage.agentResponse.knowledge_results ?? [],
        troubleshooting: sourceMessage.agentResponse.troubleshooting ?? null,
        ticket_recommendation:
          sourceMessage.agentResponse.ticket_recommendation ?? null,
        similar_tickets: sourceMessage.agentResponse.similar_tickets ?? [],
        ticket_data: ticketData,
      },
      ticket_id: sourceMessage.createdTicket?.ticket_id ?? null,
      priority: classification?.priority ?? 'Medium',
      category: classification?.category ?? 'Unclassified',
    }

    try {
      const created = await createHandoff(payload)
      window.localStorage.setItem(
        'deskai-human-support-conversation',
        created.conversation_id,
      )
      setHandoffConversationId(created.conversation_id)
      setShowHandoffPopup(true)
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === sourceMessage.id
            ? { ...message, handoffDismissed: true }
            : message,
        ),
      )
    } catch (error: unknown) {
      setHandoffError(getHandoffErrorMessage(error))
    } finally {
      setIsHandoffPending(false)
    }
  }

  function handleContinueWithAI(messageId: string) {
    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId
          ? { ...message, handoffDismissed: true }
          : message,
      ),
    )
  }

  const handleHandoffClosed = useCallback((conversationId: string) => {
    const storedConversationId = window.localStorage.getItem(
      'deskai-human-support-conversation',
    )
    if (storedConversationId === conversationId) {
      window.localStorage.removeItem('deskai-human-support-conversation')
    }
    setHandoffConversationId((currentId) =>
      currentId === conversationId ? null : currentId,
    )
    setShowHandoffPopup(false)
  }, [])

  async function handleTicketDecision(
    messageId: string,
    approved: boolean,
  ): Promise<void> {
    const message = messages.find((candidate) => candidate.id === messageId)
    if (!message) return

    const approvalId = message.agentResponse?.ticket_recommendation?.approval_id
    const originalMessage = message.originalUserMessage ?? message.content
    const ticketDetails = getTicketDetails(message)
    setMessages((currentMessages) =>
      currentMessages.map((candidate) =>
        candidate.id === messageId
          ? {
              ...candidate,
              ticketApprovalState: approved ? 'approving' : 'rejecting',
              ticketApprovalError: undefined,
            }
          : candidate,
      ),
    )

    try {
      const result = await approveTicket({
        approved,
        message: originalMessage,
        ...(approvalId ? { approval_id: approvalId } : {}),
        ...(ticketDetails ? { ticket_details: ticketDetails } : {}),
      })

      if (approved && !result.ticket) {
        throw new Error('The ticket service did not return the created ticket.')
      }

      setMessages((currentMessages) =>
        currentMessages.map((candidate) =>
          candidate.id === messageId
            ? {
                ...candidate,
                ticketApprovalState: approved ? 'approved' : 'rejected',
                createdTicket: result.ticket ?? undefined,
                ticketApprovalError: undefined,
              }
            : candidate,
        ),
      )
      if (result.ticket) {
        setTicketsRefreshKey((currentKey) => currentKey + 1)
      }
    } catch (error: unknown) {
      setMessages((currentMessages) =>
        currentMessages.map((candidate) =>
          candidate.id === messageId
            ? {
                ...candidate,
                ticketApprovalState: 'failed',
                ticketApprovalError:
                  error instanceof Error && !('response' in error)
                    ? error.message
                    : getTicketErrorMessage(error),
              }
            : candidate,
        ),
      )
    }
  }

  async function handleUpload(file: File): Promise<boolean> {
    if (isUploading || isIndexing) return false

    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!extension || !['pdf', 'docx', 'txt'].includes(extension)) {
      setDocumentError('Only PDF, DOCX, and TXT files are supported.')
      return false
    }

    setDocumentError(null)
    setDocumentNotice(null)
    setUploadingFilename(file.name)
    setUploadProgress(0)
    setIsUploading(true)
    try {
      const uploaded = await uploadDocument(file, setUploadProgress)
      if (uploaded.status === 'warming') {
        setDocumentNotice(
          uploaded.message ??
            'Embedding model is still warming up. Please wait.',
        )
        try {
          await refreshDocuments()
        } catch (error: unknown) {
          setDocumentError(
            `The uploaded document status could not be refreshed: ${getDocumentErrorMessage(error)}`,
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
      } catch (error: unknown) {
        setDocumentError(
          `The uploaded document status could not be refreshed: ${getDocumentErrorMessage(error)}`,
        )
      }
      if (uploaded.status === 'failed') {
        const stage = uploaded.stage ? ` at ${uploaded.stage}` : ''
        setDocumentError(
          `Indexing failed${stage}: ${uploaded.error ?? 'Check backend logs.'}`,
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
          <nav className="dashboard-view-tabs" aria-label="Workspace sections">
            <button
              className={activeView === 'chat' ? 'dashboard-view-tab dashboard-view-tab--active' : 'dashboard-view-tab'}
              type="button"
              aria-current={activeView === 'chat' ? 'page' : undefined}
              onClick={() => setActiveView('chat')}
            >
              AI Support Portal
            </button>
            <button
              className={activeView === 'tickets' ? 'dashboard-view-tab dashboard-view-tab--active' : 'dashboard-view-tab'}
              type="button"
              aria-current={activeView === 'tickets' ? 'page' : undefined}
              onClick={() => setActiveView('tickets')}
            >
              Admin Portal
            </button>
          </nav>
          <span
            className={`header-status ${
              performanceStatus?.warming
                ? 'header-status--warming'
                : performanceStatus?.warmup_status === 'failed'
                  ? 'header-status--failed'
                  : performanceStatus?.embedding_model_loaded
                    ? 'header-status--ready'
                    : 'header-status--checking'
            }`}
            role="status"
            aria-live="polite"
          >
            <span className="status-dot" aria-hidden="true" />
            {performanceStatus?.warming
              ? '🟡 RAG Engine Warming Up'
              : performanceStatus?.warmup_status === 'failed'
                ? '🔴 RAG Engine Unavailable'
                : performanceStatus?.embedding_model_loaded
                  ? '🟢 RAG Engine Ready'
                  : 'RAG Engine Checking'}
          </span>
          {activeView === 'chat' && (
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
          )}
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
      {documentNotice && (
        <div className="dashboard-notice" role="status" aria-live="polite">
          {documentNotice}
        </div>
      )}

      {activeView === 'chat' ? (
        <div
          className={`dashboard-workspace ${sidebarOpen ? 'dashboard-workspace--sidebar-open' : 'dashboard-workspace--sidebar-collapsed'}`}
        >
          <SidebarKnowledgeBase
            mobile
            documents={documents}
            isLoading={isDocumentsLoading}
            isUploading={isUploading}
            isIndexing={isIndexing}
            uploadProgress={uploadProgress}
            uploadingFilename={activeDocumentFilename}
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
              agentProgress={agentProgress}
              error={chatError}
              onSelectSuggestion={setDraft}
              onTicketDecision={(messageId, approved) =>
                void handleTicketDecision(messageId, approved)
              }
              onHandoff={(messageId) => void handleHandoff(messageId)}
              onContinueWithAI={handleContinueWithAI}
              handoffPending={isHandoffPending}
              handoffError={handoffError}
              handoffExists={handoffConversationId !== null}
            />
            <ChatInput
              value={draft}
              isLoading={isChatLoading}
              isUploading={isUploading}
              isIndexing={isIndexing}
              uploadProgress={uploadProgress}
              uploadingFilename={activeDocumentFilename}
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
      ) : (
        <main className="ticket-page-shell">
          <TicketsDashboard refreshKey={ticketsRefreshKey} />
        </main>
      )}
      {handoffConversationId && (
        <HumanChatWidget
          conversationId={handoffConversationId}
          onClosed={handleHandoffClosed}
        />
      )}
      {showHandoffPopup && handoffConversationId && (
        <HumanSupportPopup
          conversationId={handoffConversationId}
          onClose={() => setShowHandoffPopup(false)}
        />
      )}
    </div>
  )
}
