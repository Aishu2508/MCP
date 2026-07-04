# Gmail MCP Server (Multi-User)

A **Model Context Protocol (MCP)** server for **Gmail** that supports **many different users**, each connecting their own Gmail account. Built in Python with **FastMCP** and **FastAPI**, structured the same way as the WhatsApp MCP server, extended with per-user account management.

Each user authenticates with their own Google **App Password** over standard SMTP/IMAP (no OAuth consent flow needed). Passwords are encrypted at rest and never returned by any tool or endpoint.

## How multi-user works

Every registered Gmail account is a row tied to a `user_id` that *you* supply (your app's own user identifier — this server doesn't do authentication for you). All contacts, conversation threads, and messages are scoped to `account_id`, so different users' mailboxes never mix. One deployment can serve any number of users, each with one or more Gmail addresses connected.

## Features

- **Multi-user accounts**: `add_gmail_account` / `list_gmail_accounts` / `remove_gmail_account`.
- **Encrypted credentials**: App passwords encrypted at rest with `cryptography.Fernet`.
- **Database persistence**: Contacts, threads, and messages stored per-account in SQLite.
- **Background inbox polling**: Since Gmail has no webhook push over IMAP, a background task polls every active account's inbox on an interval and imports new mail automatically.
- **FastMCP Tools**:
  - `add_gmail_account` / `list_gmail_accounts` / `remove_gmail_account`
  - `send_email`: Sends plain-text/HTML email with optional CC/BCC/attachments, from a specific account.
  - `fetch_inbox`: Polls IMAP right now for a specific account.
  - `get_emails`: Retrieves chronological message history with a contact.
  - `search_emails`: Keyword search across subject/body.
  - `get_contact` / `list_conversations`
- **FastMCP Resources** (Read-Only):
  - `conversations://{account_id}`
  - `contacts://{account_id}`
  - `messages://{account_id}/{email}`
- **REST endpoints**: `POST/GET /accounts`, `DELETE /accounts/{id}`, `POST /accounts/{id}/fetch`, `GET /health`.

---

## Project Structure

```text
gmail-mcp-multiuser/
├── app.py                     # Entry point (FastAPI + FastMCP mounting + poller)
├── config.py                  # Pydantic Settings env loader (server-wide only)
├── requirements.txt
│
├── mcp_server/
│   ├── server.py               # FastMCP instance
│   ├── registry.py             # Imports all tools/resources to register them
│   ├── tools/
│   │   ├── accounts.py         # add/list/remove Gmail accounts (multi-user)
│   │   ├── messages.py         # send_email, fetch_inbox, get_emails, search_emails
│   │   └── contacts.py         # get_contact, list_conversations
│   └── resources/
│       └── gmail_resources.py  # Read-only resource handlers
│
├── gmail/                       # Gmail SMTP/IMAP wrappers (fixed Gmail endpoints)
│   ├── smtp_client.py           # Sends mail per-account via SMTP
│   ├── imap_client.py           # Fetches mail per-account via IMAP
│   ├── parser.py                # Parses raw RFC822 bytes into structured data
│   └── crypto.py                # Fernet encryption for stored app passwords
│
├── services/
│   ├── account_service.py
│   ├── message_service.py
│   ├── contact_service.py
│   └── conversation_service.py
│
├── database/
│   ├── database.py
│   ├── models.py                # GmailAccount, Contact, Conversation, Message
│   └── crud.py
│
├── routes/
│   ├── accounts.py              # REST account management + manual fetch trigger
│   └── health.py
│
└── utils/
    ├── logger.py
    └── validators.py
```

---

## Getting Started

### 1. Installation

```bash
cd gmail-mcp-multiuser
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Generate a Fernet encryption key and put it in `.env`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Fill in `.env`:
- `ENCRYPTION_KEY`: the generated Fernet key above (required — encrypts every user's stored app password).
- `DATABASE_URL`: defaults to local SQLite, fine for development.
- `INBOX_POLL_INTERVAL_SECONDS` / `ENABLE_BACKGROUND_POLLING`: control automatic inbox polling.

Note: there's no single Gmail account here — each user registers their own in step 4.

### 3. Run the server

```bash
python app.py
```

Exposed endpoints:
- `GET  http://localhost:8000/health`
- `POST/GET http://localhost:8000/accounts`
- `POST http://localhost:8000/accounts/{id}/fetch`
- `GET/POST http://localhost:8000/mcp/sse` — FastMCP Server-Sent-Events endpoint for MCP clients

### 4. Register a user's Gmail account

Each user needs a Google **App Password** (not their normal password):
- Enable 2-Step Verification: https://myaccount.google.com/security
- Generate an App Password: https://myaccount.google.com/apppasswords

Then call the `add_gmail_account` MCP tool (or `POST /accounts`):

```json
{
  "user_id": "user-123",
  "email": "jane@gmail.com",
  "app_password": "abcdefghijklmnop",
  "display_name": "Jane Doe"
}
```

This returns an `account_id` — use that for every subsequent `send_email`, `fetch_inbox`, `get_emails`, etc. call for this user.

### 5. Send and receive

- `send_email(account_id, to, subject, body, ...)` sends immediately via SMTP.
- New inbound mail is imported automatically by the background poller, or on demand via `fetch_inbox(account_id)` / `POST /accounts/{id}/fetch`.

---

## Notes

- App passwords are encrypted at rest but never logged or returned by any tool/endpoint.
- Users are isolated purely by `account_id` scoping in the database — there is no built-in authentication layer for *your* application's end users; add one in front of this service if it's exposed beyond trusted internal callers.
- If `fetch_inbox`/`send_email` return an authentication error, the most common cause is using a normal Gmail password instead of an App Password, or IMAP being disabled in Gmail settings (Settings → Forwarding and POP/IMAP → Enable IMAP).
