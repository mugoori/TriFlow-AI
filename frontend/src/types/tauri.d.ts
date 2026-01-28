/**
 * Tauri Global Type Declarations
 * window.__TAURI__ 전역 객체 타입 정의
 */

declare global {
  interface Window {
    __TAURI__?: {
      /**
       * Invoke a Tauri command
       */
      invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;

      /**
       * Tauri path module
       */
      path?: {
        appConfigDir: () => Promise<string>;
        appDataDir: () => Promise<string>;
        appLocalDataDir: () => Promise<string>;
        appCacheDir: () => Promise<string>;
        desktopDir: () => Promise<string>;
        documentDir: () => Promise<string>;
        downloadDir: () => Promise<string>;
        homeDir: () => Promise<string>;
        tempDir: () => Promise<string>;
      };

      /**
       * Tauri event module
       */
      event?: {
        listen: <T>(event: string, handler: (event: { payload: T }) => void) => Promise<() => void>;
        emit: (event: string, payload?: unknown) => Promise<void>;
      };

      /**
       * Tauri shell module
       */
      shell?: {
        open: (path: string) => Promise<void>;
      };

      /**
       * Tauri OS module
       */
      os?: {
        platform: () => Promise<string>;
        arch: () => Promise<string>;
        version: () => Promise<string>;
      };
    };
  }
}

export {};
