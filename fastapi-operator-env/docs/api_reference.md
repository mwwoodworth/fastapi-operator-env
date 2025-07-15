# API Reference

The FastAPI server exposes its OpenAPI schema at `/openapi.json`. When the server is running locally, you can view interactive docs at `/docs`.

To generate a typed TypeScript SDK, first fetch the schema then run `openapi-typescript-codegen`:

```bash
curl http://localhost:10000/openapi.json -o openapi.json
npm exec openapi-typescript-codegen -- \
  --input openapi.json \
  --output sdk \
  --useOptions \
  --exportSchemas
```

This creates a `sdk/` folder with the client library.
