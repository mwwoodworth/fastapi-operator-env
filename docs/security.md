# Security

Refer to [threat_model.md](threat_model.md) for the detailed threat model. Key protections include rate limiting with SlowAPI, short lived JWT access tokens, refresh rotation and double submit CSRF tokens. Always run behind HTTPS in production and restrict environment variables to trusted sources.
