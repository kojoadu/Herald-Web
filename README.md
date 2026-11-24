# Herald-Web

Standalone Streamlit website for the Herald song pool. It is intentionally separate from the Herald desktop repository.

## Features

- Email/password, Google, and Microsoft sign-in through Supabase Auth
- Dynamic church onboarding that reuses an existing canonical organization and hierarchy
- Authenticated song search, upload, preview, and download
- Latest Herald Windows release download
- Feedback with comments and one toggleable upvote per user
- Moderator report and feedback workflows

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .streamlit-secrets.toml.example .streamlit\secrets.toml
# Fill in SUPABASE_URL and SUPABASE_ANON_KEY.
streamlit run app.py
```

The portal never needs a Supabase database password or `service_role` key. Authorization is performed by the signed-in user's JWT and database Row Level Security.

Register the local and deployed Streamlit URLs in Supabase Auth. Configure the Google and Microsoft providers in Supabase, and never commit `.streamlit/secrets.toml`.

## Tests

```powershell
pytest
```
