const agents = [
  'Supervisor Agent',
  'Classification Agent',
  'Knowledge Agent',
  'Troubleshooting Agent',
]

interface AgentWorkflowCardProps {
  activeStep?: number
  completedAt?: Date
  durationMs?: number
}

export function AgentWorkflowCard({
  activeStep,
  completedAt,
  durationMs,
}: AgentWorkflowCardProps) {
  const isComplete = completedAt !== undefined
  const completionTime = completedAt?.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })

  return (
    <section
      className="agent-workflow-card"
      aria-label={isComplete ? 'AI agent workflow completed' : 'AI agent workflow in progress'}
      aria-live={isComplete ? undefined : 'polite'}
    >
      <div className="agent-workflow-heading">
        <div>
          <p className="agent-card-eyebrow">MULTI-AGENT ORCHESTRATION</p>
          <h3>AI Agent Workflow</h3>
        </div>
        <div className="agent-workflow-completion">
          {isComplete ? (
            <>
              <span className="agent-completion-status">
                <span aria-hidden="true">✓</span> Complete
              </span>
              {completionTime && <span>Completed at {completionTime}</span>}
              {durationMs !== undefined && (
                <span>{(durationMs / 1000).toFixed(1)}s total</span>
              )}
            </>
          ) : (
            <span className="agent-workflow-running">Workflow in progress</span>
          )}
        </div>
      </div>

      <ol className="agent-workflow-steps">
        {agents.map((agent, index) => {
          const stepStatus = isComplete
            ? 'complete'
            : index === activeStep
              ? 'running'
              : activeStep !== undefined && index < activeStep
                ? 'complete'
                : 'waiting'

          return (
            <li
              className={`agent-workflow-step agent-workflow-step--${stepStatus}`}
              key={agent}
              aria-current={stepStatus === 'running' ? 'step' : undefined}
            >
              <span className="agent-workflow-marker" aria-hidden="true">
                {stepStatus === 'complete' ? '✓' : null}
              </span>
              <span className="agent-workflow-copy">
                <span className="agent-workflow-label">{agent}</span>
                <span className={`agent-workflow-state agent-workflow-state--${stepStatus}`}>
                  {stepStatus === 'complete'
                    ? 'Complete'
                    : stepStatus === 'running'
                      ? '⏳ Running...'
                      : 'Waiting'}
                </span>
              </span>
              <span className="sr-only">
                {stepStatus === 'complete'
                  ? 'Complete'
                  : stepStatus === 'running'
                    ? 'Running'
                    : 'Waiting'}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
