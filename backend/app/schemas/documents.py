"""Documents API DTOs (M3.3).

`DocumentInfo` is the single response shape for both `GET /documents`
(as a list) and `POST /documents` / `DELETE /documents/{id}`. No request
body schema lives here — `POST /documents` is a multipart upload and the
route handler consumes the `UploadFile` directly.

`status` is serialised as the string value of `DocumentStatus` (a
`StrEnum`); we stop short of declaring a `Literal[...]` here because the
canonical enum lives in `app.models.document` and we don't want a parallel
copy that can drift.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentInfo(BaseModel):
    """Public view of a `Document` row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime: str
    size: int
    status: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


__all__ = ["DocumentInfo"]
