declare module 'react' {
  export const useState: any;
  export const useEffect: any;
  export interface FormEvent<T = any> {}
  export type ReactNode = any;
  const React: any;
  export default React;
}

declare namespace React {
  type ReactNode = any;
  interface FormEvent<T = any> {}
}

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}
declare module 'react/jsx-runtime' {
  export default any;
}
declare module 'next/link' {
  const Link: any;
  export default Link;
}
