# Quick Start

These steps get the Operator running locally.

1. Install Python deps and create an environment file:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. Define at least one user for JWT auth:
   ```bash
   export AUTH_USERS='{"admin":"<hashed-password>"}'
   # generate a hash using:
   # python -c 'from passlib.hash import pbkdf2_sha256; print(pbkdf2_sha256.hash("secret"))'
   export ADMIN_USERS=admin
   ```
3. Start the API server:
   ```bash
   uvicorn main:app --reload --port 10000
   ```
4. Visit `http://localhost:10000/docs` for interactive API docs.
