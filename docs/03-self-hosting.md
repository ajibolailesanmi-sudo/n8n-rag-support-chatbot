# Self-hosting n8n (free)

n8n Cloud is the easiest home for these workflows, but n8n itself is free to self-host. This guide sets it up on a Windows PC with Docker Desktop. The same `docker-compose.yml` works on a Mac, a Linux server or a small VPS.

## 1. Install Docker Desktop

1. Download Docker Desktop for Windows from docker.com and install it (it will ask to enable WSL 2; accept and restart if asked).
2. Start Docker Desktop and wait until it says "Engine running".

## 2. Start n8n

1. Download this repository (Code > Download ZIP on GitHub) and unzip it, for example to `C:\n8n-support-chatbot`.
2. Copy `.env.example` to `.env` and replace `N8N_ENCRYPTION_KEY` with a long random string. In PowerShell this prints one: `-join ((48..57)+(97..122) | Get-Random -Count 48 | % {[char]$_})`.
3. In PowerShell, in that folder: `docker compose up -d`
4. Open http://localhost:5678 and create the owner account (this is local to your PC).

Updating n8n later: `docker compose pull` then `docker compose up -d`. Your workflows and credentials live in the `n8n_data` volume and survive updates.

## 3. Import the workflows

Follow `docs/02-setup-guide.md` from section 4 (credentials) onwards. Everything that calls out from n8n (Supabase, Gemini, Google, Slack, email) works from your PC without any further setup.

## 4. Things that must reach your PC from the internet

Two parts need a public address: the WhatsApp webhook (Meta must call n8n) and the chat widget when it is embedded on a website other than your PC. The hosted chat page and the test runner work on localhost.

The free option is a Cloudflare quick tunnel:

1. Install cloudflared (`winget install Cloudflare.cloudflared`).
2. Run `cloudflared tunnel --url http://localhost:5678`. It prints a random `https://....trycloudflare.com` address.
3. Put that address into `.env` as `WEBHOOK_URL` (with a trailing slash), set `N8N_HOST` to the host part and `N8N_PROTOCOL=https`, then `docker compose up -d` again.
4. Re-publish `11 - WhatsApp` so Meta receives the new webhook address.

Quick tunnels get a new address every time they start; a named tunnel on your own domain keeps one address and is also free.

## 5. Keeping it running

n8n runs while the PC is on and Docker Desktop is running. For a demo that is enough; for a team, move the same compose file to a small VPS (about $5 a month) so it runs around the clock, and switch `.env` to that server's address.
