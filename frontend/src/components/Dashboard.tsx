import { useCallback, useEffect, useState } from 'react'
import { ChatContainer } from './ChatContainer'
import { ChatInput } from './ChatInput'
import { TicketsDashboard } from '../pages/TicketsDashboard'
import {
  getChatErrorMessage,
  getPerformanceStatus,
  sendAgentChatMessage,
} from '../services/api'
import type { PerformanceStatus } from '../services/api'
import type { AgentRefinementContext, ChatMessage } from '../types/chat'
import type { TicketCreateRequest, TicketPriority } from '../types/ticket'
import {
  approveTicket,
  createTicket,
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
import { formatServiceRequestId } from '../utils/handoff'
import '../human-support.css'

const greeting: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: "Hello, I'm your AI Service Desk Assistant. How can I help you today?",
  timestamp: new Date(),
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

function buildRefinementContext(
  messages: ChatMessage[],
): AgentRefinementContext {
  const conversationHistory = messages
    .filter((message) => message.id !== 'welcome')
    .slice(-10)
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, 2000),
      ...(message.satisfaction ? { satisfaction: message.satisfaction } : {}),
    }))

  const previousAnswer = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === 'assistant' &&
        message.satisfaction === 'not_helpful' &&
        message.agentResponse,
    )
  const response = previousAnswer?.agentResponse
  const originalQuestion = messages.find((message) => message.role === 'user')
  return {
    original_question:
      originalQuestion?.content ?? previousAnswer?.originalUserMessage ?? '',
    previous_response: previousAnswer?.content ?? '',
    conversation_history: conversationHistory,
    classification: response?.classification ?? {},
    troubleshooting: response?.troubleshooting ?? {},
    knowledge_sources: response?.knowledge_sources?.slice(0, 8) ?? [],
    knowledge_results:
      response?.knowledge_results?.slice(0, 4).map((item) => ({
        content: item.content.slice(0, 1200),
        metadata: item.metadata,
        score: item.score,
      })) ?? [],
    ticket_recommendation: response?.ticket_recommendation ?? null,
    similar_tickets: response?.similar_tickets?.slice(0, 5) ?? [],
      ticket_status: response?.ticket_status ?? null,
  }
}

interface DashboardProps {
  onNavigate: (destination: '/' | '/login' | '/dashboard') => void
}

interface LocalConversation {
  id: string
  title: string
  messages: ChatMessage[]
}

export function Dashboard({ onNavigate }: DashboardProps) {
  const [activeView, setActiveView] = useState<'chat' | 'tickets'>('chat')
  const [handoffConversationId, setHandoffConversationId] = useState<string | null>(null)
  const [handoffDisplayId, setHandoffDisplayId] = useState<string | null>(null)
  const [handoffRestored, setHandoffRestored] = useState(false)
  const [showHandoffPopup, setShowHandoffPopup] = useState(false)
  const [isHandoffPending, setIsHandoffPending] = useState(false)
  const [handoffError, setHandoffError] = useState<string | null>(null)
  const [ticketsRefreshKey, setTicketsRefreshKey] = useState(0)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting])
  const [activeConversationId, setActiveConversationId] = useState('conversation-initial')
  const [conversations, setConversations] = useState<LocalConversation[]>([
    {
      id: 'conversation-initial',
      title: 'New conversation',
      messages: [greeting],
    },
  ])
  const [dissatisfactionCount, setDissatisfactionCount] = useState(0)
  const [awaitingClarification, setAwaitingClarification] = useState(false)
  const [draft, setDraft] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [performanceStatus, setPerformanceStatus] =
    useState<PerformanceStatus | null>(null)

  useEffect(() => {
    const firstQuestion = messages.find((message) => message.role === 'user')?.content
    const title = firstQuestion
      ? firstQuestion.length > 38
        ? `${firstQuestion.slice(0, 38).trimEnd()}…`
        : firstQuestion
      : 'New conversation'
    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === activeConversationId
          ? { ...conversation, title, messages }
          : conversation,
      ),
    )
  }, [activeConversationId, messages])

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
        setHandoffRestored(true)
        setHandoffConversationId(savedConversationId)
        setHandoffDisplayId(formatServiceRequestId(detail.conversation.id))
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

  async function handleSend() {
    const message = draft.trim()
    if (!message || isChatLoading) return
    const isClarification = awaitingClarification
    const refinementContext = isClarification
      ? buildRefinementContext(messages)
      : undefined

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
    setAwaitingClarification(false)
    setIsChatLoading(true)

    try {
      const result = await sendAgentChatMessage(message, refinementContext)
      const completedAt = new Date()
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: result.response ?? '',
          agentResponse: result,
          originalUserMessage: refinementContext
            ? `${refinementContext.original_question}\n\nClarification: ${message}`
            : message,
          timestamp: completedAt,
        },
      ])
    } catch (error: unknown) {
      setChatError(getChatErrorMessage(error))
      if (isClarification) setAwaitingClarification(true)
    } finally {
      setIsChatLoading(false)
    }
  }

  function handleAnswerFeedback(messageId: string, helpful: boolean) {
    const answer = messages.find(
      (message) => message.id === messageId && message.agentResponse,
    )
    if (!answer?.agentResponse) return

    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId
          ? { ...message, satisfaction: helpful ? 'helpful' : 'not_helpful' }
          : message,
      ),
    )

    if (helpful) {
      setDissatisfactionCount(0)
      setAwaitingClarification(false)
      return
    }

    const nextDissatisfactionCount = dissatisfactionCount + 1
    setDissatisfactionCount(nextDissatisfactionCount)
    if (nextDissatisfactionCount === 1) {
      setAwaitingClarification(true)
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            "I’m sorry the solution did not resolve the issue.\n\nPlease tell me what is still not working or provide additional details.",
          timestamp: new Date(),
        },
      ])
      return
    }

    setAwaitingClarification(false)
    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        content:
          'I’m sorry, but I have not been able to resolve this issue.',
        agentResponse: answer.agentResponse,
        originalUserMessage:
          messages.find((message) => message.role === 'user')?.content ??
          answer.originalUserMessage ??
          answer.content,
        createdTicket: answer.createdTicket,
        timestamp: new Date(),
        handoffRecommended: true,
      },
    ])
  }

  async function handleHandoff(messageId: string) {
    if (isHandoffPending || handoffConversationId) return
    const sourceMessage = messages.find((message) => message.id === messageId)
    if (!sourceMessage?.agentResponse) return

    setIsHandoffPending(true)
    setHandoffError(null)
    try {
      let ticket = sourceMessage.createdTicket
      if (!ticket) {
        const ticketRequest = getTicketDetails(sourceMessage)
        if (!ticketRequest) {
          setHandoffError(
            'I could not prepare a support ticket from this conversation. Please try again.',
          )
          return
        }

        try {
          ticket = await createTicket(ticketRequest)
        } catch (error: unknown) {
          setHandoffError(
            `The support ticket could not be created: ${getTicketErrorMessage(error)}`,
          )
          return
        }
        setTicketsRefreshKey((currentKey) => currentKey + 1)
        setMessages((currentMessages) =>
          currentMessages.map((message) =>
            message.id === sourceMessage.id
              ? { ...message, createdTicket: ticket }
              : message,
          ),
        )
      }

      const conversationMessages: CreateHandoffRequest['messages'] = messages.map(
        (message) => ({
          role: message.role,
          content: message.content,
          timestamp: message.timestamp.toISOString(),
          metadata: {
            ...(message.agentResponse
              ? { agent_response: message.agentResponse }
              : {}),
            ...(message.classification
              ? { classification: message.classification }
              : {}),
            ...(message.originalUserMessage
              ? { original_user_message: message.originalUserMessage }
              : {}),
            ...(message.createdTicket
              ? { ticket_data: message.createdTicket }
              : {}),
            ...(message.id === sourceMessage.id && ticket
              ? { ticket_data: ticket }
              : {}),
            ...(message.satisfaction
              ? { satisfaction_feedback: message.satisfaction }
              : {}),
            ...(message.handoffRecommended
              ? { escalation_reason: 'Repeated negative answer feedback.' }
              : {}),
          },
        }),
      )
      const classification = sourceMessage.agentResponse.classification
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
          ticket_data: ticket,
          dissatisfaction_count: dissatisfactionCount,
          feedback_history: messages
            .filter((message) => message.satisfaction)
            .map((message) => ({
              role: message.role,
              content: message.content,
              satisfaction: message.satisfaction,
            })),
          escalation_reason: 'The user marked two AI responses as not helpful.',
        },
        ticket_id: ticket?.ticket_id ?? null,
        priority: classification?.priority ?? 'Medium',
        category: classification?.category ?? 'Unclassified',
      }

      const created = await createHandoff(payload)
      window.localStorage.setItem(
        'deskai-human-support-conversation',
        created.conversation_id,
      )
      setHandoffConversationId(created.conversation_id)
      setHandoffDisplayId(formatServiceRequestId(created.id))
      setHandoffRestored(false)
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
    setDissatisfactionCount(0)
    setAwaitingClarification(false)
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
    setHandoffDisplayId(null)
    setHandoffRestored(false)
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

  function startNewChat() {
    const id = `conversation-${window.crypto.randomUUID()}`
    setConversations((current) => [
      { id, title: 'New conversation', messages: [greeting] },
      ...current,
    ])
    setActiveConversationId(id)
    setMessages([greeting])
    setDraft('')
    setChatError(null)
    setAwaitingClarification(false)
    setDissatisfactionCount(0)
    setActiveView('chat')
  }

  function openConversation(conversation: LocalConversation) {
    setActiveConversationId(conversation.id)
    setMessages(conversation.messages)
    setDraft('')
    setChatError(null)
    setAwaitingClarification(false)
    setActiveView('chat')
  }

  const latestAgentMessage = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.agentResponse)
  const latestResponse = latestAgentMessage?.agentResponse
  const latestClassification = latestResponse?.classification
  const latestTicketMessage = [...messages]
    .reverse()
    .find((message) => message.createdTicket || message.agentResponse?.ticket_status)
  const latestTicket = latestTicketMessage?.createdTicket
  const ticketStatus =
    latestTicket?.status ??
    latestTicketMessage?.agentResponse?.ticket_status?.status ??
    null
  const recentConversations = conversations
    .filter(
      (conversation) =>
        conversation.title !== 'New conversation' ||
        conversation.id === activeConversationId,
    )
    .slice(0, 6)

  return (
    <div className="dashboard-shell dashboard-shell--app">
      <header className="dashboard-header">
        <button className="dashboard-brand" type="button" onClick={() => onNavigate('/')}>
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M16 3.5 19.1 12l8.4 4-8.4 3.1L16 28.5 12.9 19l-8.4-3 8.4-4L16 3.5Z" />
              <path d="m25.5 3 .9 2.6L29 6.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" />
            </svg>
          </span>
          <div className="dashboard-brand-copy">
            <h1>DeskAI</h1>
            <p>Agentic AI Service Desk</p>
          </div>
        </button>
        <div className="dashboard-header-actions">
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
              ? 'AI engine warming up'
              : performanceStatus?.warmup_status === 'failed'
                ? 'AI engine unavailable'
                : performanceStatus?.embedding_model_loaded
                  ? 'AI engine ready'
                  : 'Connecting to AI'}
          </span>
          <button className="dashboard-home-link" type="button" onClick={() => onNavigate('/')}>
            <span aria-hidden="true">⌂</span> Home
          </button>
          <div className="workspace-avatar" aria-label="Demo workspace">D</div>
        </div>
      </header>

      <div className="app-shell-layout">
        <aside className="app-sidebar">
          <button className="new-chat-button" type="button" onClick={startNewChat} disabled={isChatLoading}>
            <span aria-hidden="true">＋</span> New chat
            <kbd>⌘ K</kbd>
          </button>
          <p className="app-sidebar-label">WORKSPACE</p>
          <nav className="app-primary-nav" aria-label="Workspace navigation">
            <button
              className={activeView === 'chat' ? 'app-nav-item app-nav-item--active' : 'app-nav-item'}
              type="button"
              aria-current={activeView === 'chat' ? 'page' : undefined}
              onClick={() => setActiveView('chat')}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 4.5h13v9h-7l-4 3v-3h-2z" /><path d="M6.5 8h7M6.5 10.5h4" /></svg>
              AI Support
              <span className="nav-item-badge">AI</span>
            </button>
            <button
              className={activeView === 'tickets' ? 'app-nav-item app-nav-item--active' : 'app-nav-item'}
              type="button"
              aria-current={activeView === 'tickets' ? 'page' : undefined}
              onClick={() => setActiveView('tickets')}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3.5" y="3.5" width="13" height="13" rx="2" /><path d="M7 7h6M7 10h6M7 13h3" /></svg>
              Admin Portal
            </button>
          </nav>

          <div className="app-sidebar-section">
            <div className="app-sidebar-section-heading">
              <p className="app-sidebar-label">RECENT CONVERSATIONS</p>
              <span>{recentConversations.length}</span>
            </div>
            <div className="recent-conversation-list">
              {recentConversations.map((conversation) => (
                <button
                  className={activeConversationId === conversation.id ? 'recent-conversation recent-conversation--active' : 'recent-conversation'}
                  type="button"
                  key={conversation.id}
                  onClick={() => openConversation(conversation)}
                  disabled={isChatLoading}
                  title={conversation.title}
                >
                  <span className="recent-conversation-icon" aria-hidden="true">◌</span>
                  <span>{conversation.title}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="app-sidebar-section app-quick-actions">
            <p className="app-sidebar-label">QUICK ACTIONS</p>
            <button type="button" onClick={() => { setActiveView('chat'); setDraft('I need help connecting to the VPN.') }}>
              <span aria-hidden="true">⌁</span> Troubleshoot an issue
            </button>
            <button type="button" onClick={() => { setActiveView('chat'); setDraft('I have a question about my account.') }}>
              <span aria-hidden="true">✦</span> Ask DeskAI
            </button>
          </div>

          <div className="app-sidebar-footer">
            <span className="workspace-avatar workspace-avatar--sidebar">D</span>
            <div><strong>Demo workspace</strong><span>Service desk</span></div>
            <span className="sidebar-footer-menu" aria-hidden="true">···</span>
          </div>
        </aside>

        {activeView === 'chat' ? (
          <div className="dashboard-workspace dashboard-workspace--chat-only">
            <main className="chat-workspace">
              <ChatContainer
                messages={messages}
                isLoading={isChatLoading}
                error={chatError}
                onSelectSuggestion={setDraft}
                onTicketDecision={(messageId, approved) =>
                  void handleTicketDecision(messageId, approved)
                }
                onAnswerFeedback={handleAnswerFeedback}
                onHandoff={(messageId) => void handleHandoff(messageId)}
                onContinueWithAI={handleContinueWithAI}
                handoffPending={isHandoffPending}
                handoffError={handoffError}
                handoffExists={handoffConversationId !== null}
              />
              <ChatInput
                value={draft}
                isLoading={isChatLoading}
                onChange={setDraft}
                onSubmit={handleSend}
              />
              <p className="composer-privacy">
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <rect x="3.5" y="7" width="9" height="7" rx="1.5" />
                  <path d="M5.5 7V5a2 2 0 0 1 4 0v2" />
                </svg>
                DeskAI can make mistakes. Check important information.
              </p>
            </main>

            <aside className="assistant-context-panel" aria-label="Conversation context">
              <div className="context-panel-heading">
                <div><span className="context-panel-kicker">LIVE CONTEXT</span><h2>Issue overview</h2></div>
                <span className="context-live-dot" title="Conversation context" />
              </div>
              <section className="context-card">
                <div className="context-card-heading"><span className="context-card-icon">◈</span><h3>Classification</h3></div>
                <dl>
                  <div><dt>Category</dt><dd>{latestClassification?.category ?? 'Not classified yet'}</dd></div>
                  {latestClassification?.subcategory && <div><dt>Type</dt><dd>{latestClassification.subcategory}</dd></div>}
                  {latestClassification?.assigned_group && <div><dt>Assigned group</dt><dd>{latestClassification.assigned_group}</dd></div>}
                </dl>
                <div className="context-priority-row"><span>Priority</span><strong className={`context-priority context-priority--${(latestClassification?.priority ?? 'unset').toLowerCase()}`}>{latestClassification?.priority ?? '—'}</strong></div>
              </section>
              <section className="context-card">
                <div className="context-card-heading"><span className="context-card-icon context-card-icon--blue">▤</span><h3>Knowledge sources</h3><span className="context-count">{latestResponse?.knowledge_sources?.length ?? 0}</span></div>
                {latestResponse?.knowledge_sources?.length ? (
                  <ul className="context-source-list">
                    {latestResponse.knowledge_sources.slice(0, 4).map((source, index) => (
                      <li key={`${source}-${index}`}><span>PDF</span><strong>{source}</strong></li>
                    ))}
                  </ul>
                ) : <p className="context-empty">Sources will appear here when DeskAI finds relevant guidance.</p>}
              </section>
              <section className="context-card">
                <div className="context-card-heading"><span className="context-card-icon context-card-icon--green">▣</span><h3>Ticket information</h3></div>
                {latestTicket ? (
                  <div className="context-ticket">
                    <span>{latestTicket.ticket_number ?? latestTicket.ticket_id}</span>
                    <strong>{latestTicket.title}</strong>
                    <small>{latestTicket.assigned_group}</small>
                  </div>
                ) : latestTicketMessage?.agentResponse?.ticket_status ? (
                  <div className="context-ticket">
                    <span>{latestTicketMessage.agentResponse.ticket_status.ticket_id}</span>
                    <strong>{latestTicketMessage.agentResponse.ticket_status.assigned_group ?? 'Service desk'}</strong>
                  </div>
                ) : <p className="context-empty">A ticket will appear here if one is created.</p>}
                <div className="context-status-row"><span>Status</span><strong className={ticketStatus ? 'context-status context-status--active' : 'context-status'}><i />{ticketStatus ?? 'No ticket'}</strong></div>
              </section>
              <div className="context-assurance"><span>✦</span><p><strong>AI + human support</strong><br />Escalate to a person whenever you need.</p></div>
            </aside>
          </div>
        ) : (
          <main className="ticket-page-shell">
            <TicketsDashboard
              refreshKey={ticketsRefreshKey}
              performanceStatus={performanceStatus}
            />
          </main>
        )}
      </div>

      {handoffConversationId && (
        <HumanChatWidget
          conversationId={handoffConversationId}
          initiallyMinimized={handoffRestored}
          onClosed={handleHandoffClosed}
        />
      )}
      {showHandoffPopup && handoffConversationId && handoffDisplayId && (
        <HumanSupportPopup
          displayId={handoffDisplayId}
          onClose={() => setShowHandoffPopup(false)}
        />
      )}
    </div>
  )
}
