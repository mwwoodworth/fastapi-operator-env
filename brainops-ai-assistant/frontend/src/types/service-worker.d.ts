/// <reference lib="webworker" />

export interface ServiceWorkerGlobalScopeEventMap {
  activate: ExtendableEvent;
  fetch: FetchEvent;
  install: ExtendableEvent;
  message: ExtendableMessageEvent;
  messageerror: MessageEvent;
  notificationclick: NotificationEvent;
  notificationclose: NotificationEvent;
  push: PushEvent;
  pushsubscriptionchange: Event;
  sync: SyncEvent;
}

declare global {
  interface Window {
    workbox: {
      register: () => void;
      addEventListener: (event: string, callback: () => void) => void;
      messageSkipWaiting: () => void;
    };
  }
}