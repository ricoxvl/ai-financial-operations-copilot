"""Generate a fresh local approval token and .env file; never checks in secrets."""
import secrets
from pathlib import Path

root=Path(__file__).resolve().parent.parent
target=root/'.env'
if target.exists():
    print('.env already exists; keeping your current settings.')
    print('Find APP_APPROVAL_TOKEN in .env when the dashboard asks for it.')
else:
    token=secrets.token_urlsafe(32)
    target.write_text('\n'.join([
        '# Generated local development credentials. Never commit this file.',
        'APP_DATABASE_URL=sqlite:///./copilot.db',
        f'APP_APPROVAL_TOKEN={token}',
        'APP_CHECKPOINT_PATH=./copilot-checkpoints.sqlite',
        'OPENAI_API_KEY=',
        'OPENAI_MODEL=gpt-4.1-mini',
        'APP_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173',
        '']))
    try:target.chmod(0o600)
    except OSError:pass
    print('Created .env with a randomly generated local approval token.')
    print('APP_APPROVAL_TOKEN = '+token)
    print('Copy this into the approval dialog when reviewing a proposal. Do not share it.')
