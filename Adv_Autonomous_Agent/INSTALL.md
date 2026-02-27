# INSTALLATION GUIDE

Welcome to the **Elite Consulting Executive Board** installation. Follow these steps to set up your boardroom.

## 1. Prerequisites

- **Python 3.10+** installed.
- An **N8N instance** (Cloud or Self-Hosted).
- **Google Cloud Console** access (for Workspace automation).

## 2. Environment Setup

1. Clone or download the project folder.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`.
4. Fill in your `WEBHOOK_URL` from N8N.

## 3. N8N Deployment

1. Log in to your N8N instance.
2. Go to **Settings > Workflows > Import from File**.
3. Select `elite_council_blueprint.json` from this folder.
4. Activate the workflow and copy the **Production Webhook URL**.

## 4. Launch

Run the board interface:

```bash
python ui.py
```

Your CEO is now ready to receive instructions.
