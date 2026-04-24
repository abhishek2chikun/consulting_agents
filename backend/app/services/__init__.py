"""Service layer.

Thin domain services over the ORM. Each service takes an explicit
`AsyncSession` in its constructor (no global session lookup) so that
callers — request handlers in M2.4+, agent runtime in later milestones —
control transaction scope.
"""
