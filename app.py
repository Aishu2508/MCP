import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.database import Base, engine, SessionLocal
from database import crud
from mcp_server.server import mcp
import mcp_server.registry  # Import registry to load tools and resources
from routes import health, accounts
from services.message_service import MessageService
from utils.logger import setup_logger

logger = setup_logger(__name__)
message_service = MessageService()


async def _background_inbox_poller():
    """Periodically polls every registered, active user's Gmail inbox via IMAP.

    Gmail has no native push/webhook mechanism over IMAP, so new mail is
    picked up by polling on an interval for each account across all users.
    """
    interval = settings.INBOX_POLL_INTERVAL_SECONDS
    logger.info(f"Background inbox poller started (interval={interval}s).")
    while True:
        try:
            with SessionLocal() as db:
                accounts_list = crud.list_all_active_accounts(db)
                for account in accounts_list:
                    try:
                        result = await message_service.fetch_inbox(db, account.id, limit=20)
                        new_count = result.get("count", 0)
                        if new_count:
                            logger.info(f"Account {account.id} ({account.email}): imported {new_count} new message(s).")
                    except Exception as e:
                        logger.error(f"Polling failed for account {account.id} ({account.email}): {e}")
        except Exception as e:
            logger.error(f"Background inbox poller iteration failed: {e}")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize SQLite database tables on startup
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    # 2. Start the background IMAP polling task (if enabled)
    poller_task = None
    if settings.ENABLE_BACKGROUND_POLLING:
        poller_task = asyncio.create_task(_background_inbox_poller())

    # 3. Run FastMCP context manager lifespan
    logger.info("Starting FastMCP server session lifespan...")
    async with mcp.lifespan():
        yield
    logger.info("FastMCP server session lifespan stopped.")

    # 4. Stop the background poller on shutdown
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


# Initialize parent FastAPI application
app = FastAPI(
    title="Gmail Multi-User MCP Server Gateway",
    description="FastAPI service hosting multi-user Gmail account management and mounting FastMCP over SSE",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints
app.include_router(health.router)
app.include_router(accounts.router)

# Mount FastMCP HTTP/SSE app.
# AI clients (such as Cursor or Claude Desktop) can connect to: http://localhost:8000/mcp/sse
mcp_app = mcp.http_app(transport="sse")
app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}...")
    uvicorn.run("app:app", host=settings.HOST, port=settings.PORT, reload=True)
