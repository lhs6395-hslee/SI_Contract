"use client";

import { useState, useEffect, useCallback, createContext, useContext } from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

interface Toast {
  id: number;
  type: "success" | "error" | "info";
  message: string;
}

interface ToastCtx {
  toast: (type: Toast["type"], message: string) => void;
}

const ToastContext = createContext<ToastCtx>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let _nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: Toast["type"], message: string) => {
    const id = ++_nextId;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const Icon = { success: CheckCircle, error: AlertCircle, info: Info };
  const colors = {
    success: "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-200",
    error: "bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200",
    info: "bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200",
  };

  return (
    <ToastContext value={{ toast: addToast }}>
      {children}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => {
          const I = Icon[t.type];
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg text-sm animate-in fade-in slide-in-from-bottom-2 ${colors[t.type]}`}
            >
              <I className="h-4 w-4 shrink-0" />
              <span className="flex-1">{t.message}</span>
              <button onClick={() => remove(t.id)} className="shrink-0 opacity-60 hover:opacity-100">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext>
  );
}
