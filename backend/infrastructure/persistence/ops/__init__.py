"""Gate 09 operational infrastructure stores.

Concrete relational implementations of the application-layer ops ports:

- ``IdempotencyStore``         — client idempotency reservations
- ``WebhookReceiptStore``      — provider delivery deduplication
- ``AuditStore``               — append-only compliance trail
- ``OutboxWorkerStore``        — transactional outbox claim/mark
- ``ChannelTenantResolver``    — phone → (tenant, patient) routing anchor
"""