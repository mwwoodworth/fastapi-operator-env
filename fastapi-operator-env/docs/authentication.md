# Authentication

The API uses JSON Web Tokens with short expiration times. Obtain a token by POSTing to `/auth/token` with form data `username` and `password`.

Successful authentication returns an `access_token` and a `csrf_token` which must be included in the `Authorization` header and `X-CSRF-Token` header for state changing requests.

Tokens can also be stored in `HttpOnly` cookies when running in a browser. Use `/auth/refresh` to rotate tokens and `/auth/logout` to clear them.
