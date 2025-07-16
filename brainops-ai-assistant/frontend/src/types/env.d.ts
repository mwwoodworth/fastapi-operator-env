declare namespace NodeJS {
  interface ProcessEnv {
    NEXT_PUBLIC_API_URL?: string;
    NEXT_PUBLIC_WEBSOCKET_URL?: string;
    NODE_ENV: 'development' | 'production' | 'test';
  }
}