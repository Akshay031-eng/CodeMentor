import logging

from supabase import Client, create_client

import config

logger = logging.getLogger(__name__)


if not config.SUPABASE_URL:
    raise ValueError("SUPABASE_URL is missing from Backend/.env")

if not config.SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) is missing from Backend/.env"
    )


supabase: Client = create_client(
    config.SUPABASE_URL,
    config.SUPABASE_KEY,
)

logger.info("Supabase client ready (%s)", config.SUPABASE_URL)
