class TicketServiceError(RuntimeError):
    pass


class TicketNotFoundError(TicketServiceError):
    pass


class PendingApprovalNotFoundError(TicketServiceError):
    pass
