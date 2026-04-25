"""ORM model registry.

One ORM class per file. This package re-exports them so that:

1. Application code can `from app.models import User, SettingKV`.
2. Alembic's `target_metadata = Base.metadata` sees every model after
   `import app.models` (importing this package transitively imports each
   class, which registers it on `Base.metadata`).

Add new models here as they are introduced.
"""

from app.models.artifact import Artifact
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.event import Event
from app.models.evidence import Evidence, EvidenceKind
from app.models.gate import Gate
from app.models.message import Message, MessageRole
from app.models.provider_key import ProviderKey
from app.models.run import Run, RunStatus
from app.models.settings_kv import SettingKV
from app.models.task_type import TaskType
from app.models.user import SINGLETON_USER_ID, User

__all__ = [
    "SINGLETON_USER_ID",
    "Artifact",
    "Chunk",
    "Document",
    "DocumentStatus",
    "Evidence",
    "EvidenceKind",
    "Event",
    "Gate",
    "Message",
    "MessageRole",
    "ProviderKey",
    "Run",
    "RunStatus",
    "SettingKV",
    "TaskType",
    "User",
]
