"""Replace SmartRecruiters JSON API links with public job pages.

Revision ID: 005_repair_smartrecruiters_urls
Revises: 004_embedding_hash
Create Date: 2026-08-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005_repair_smartrecruiters_urls"
down_revision: Union[str, None] = "004_embedding_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET apply_url =
            'https://jobs.smartrecruiters.com/'
            || split_part(external_id, ':', 1)
            || '/'
            || split_part(external_id, ':', 2)
            || CASE
                WHEN trim(both '-' from lower(regexp_replace(title, '[^a-zA-Z0-9]+', '-', 'g'))) = ''
                    THEN ''
                ELSE '-' || trim(both '-' from lower(regexp_replace(title, '[^a-zA-Z0-9]+', '-', 'g')))
               END
            || '?oga=true'
        WHERE source = 'smartrecruiters'
          AND apply_url ILIKE '%api.smartrecruiters.com/%'
          AND external_id LIKE '%:%'
        """
    )


def downgrade() -> None:
    # This is a corrective data migration. Restoring broken API URLs is intentionally unsupported.
    pass
