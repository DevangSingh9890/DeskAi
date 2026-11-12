import { useState } from 'react'
import { ChatWindow } from './components/ChatWindow'
import { KnowledgeBase } from './components/KnowledgeBase'
import { getChatErrorMessage, sendChatMessage } from './services/api'
import type { ChatMessage } from './types/chat'
import './App.css'

type Page = 'chat' | 'knowledge'

const greeting: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: "Hello, I'm your AI Service Desk Assistant. How can I help you today?",
  timestamp: new Date(),
}

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([greeting])
  const [draft, setDraft] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState<Page>('chat')

  async function handleSend() {
    const message = draft.trim()
    if (!message || isLoading) return

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: new Date(),
    }

    setMessages((currentMessages) => [...currentMessages, userMessage])
    setDraft('')
    setError(null)
    setIsLoading(true)

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
    } catch (requestError: unknown) {
      setError(getChatErrorMessage(requestError))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/" aria-label="DeskAI home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M16 3.5 19.1 12l8.4 4-8.4 3.1L16 28.5 12.9 19l-8.4-3 8.4-4L16 3.5Z" />
              <path d="m25.5 3 .9 2.6L29 6.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" />
            </svg>
          </span>
          <span className="brand-name">Desk<span>AI</span></span>
        </a>

        <div className="header-divider" aria-hidden="true" />
        <span className="header-product-name">AI Service Desk Assistant</span>

        <nav className="app-navigation" aria-label="Main navigation">
          <button
            className={`navigation-link ${page === 'chat' ? 'navigation-link--active' : ''}`}
            type="button"
            aria-current={page === 'chat' ? 'page' : undefined}
            onClick={() => setPage('chat')}
          >
            Chat
          </button>
          <button
            className={`navigation-link ${page === 'knowledge' ? 'navigation-link--active' : ''}`}
            type="button"
            aria-current={page === 'knowledge' ? 'page' : undefined}
            onClick={() => setPage('knowledge')}
          >
            Knowledge Base
          </button>
        </nav>

        <div className="header-status">
          <span className="status-dot" aria-hidden="true" />
          Here to help
        </div>
      </header>

      <div className="page-content">
        {page === 'chat' ? (
          <>
            <div className="page-overline">
              <span className="page-overline-line" />
              <span>SUPPORT, MADE SIMPLE</span>
              <span className="page-overline-line" />
            </div>
            <ChatWindow
              messages={messages}
              draft={draft}
              isLoading={isLoading}
              error={error}
              onDraftChange={setDraft}
              onSend={handleSend}
              onSelectSuggestion={setDraft}
            />
          </>
        ) : (
          <KnowledgeBase />
        )}
        <footer className="page-footer">
          <span>Need urgent help?</span>
          <span>Contact your IT support team directly.</span>
        </footer>
      </div>
    </div>
  )
}

export default App
