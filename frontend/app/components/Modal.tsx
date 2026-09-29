"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** `drawer` slides in from the right edge at full height. */
  variant?: "modal" | "drawer";
}

const SHELL: Record<NonNullable<ModalProps["variant"]>, string> = {
  modal:
    "m-auto max-h-[90vh] w-[min(94vw,760px)] rounded-2xl",
  drawer:
    "my-0 ml-auto mr-0 h-full max-h-none w-[min(100vw,680px)] rounded-none rounded-l-2xl border-r-0",
};

/**
 * Native <dialog>: the browser provides focus trapping, Esc-to-close and the
 * backdrop. Children mount only while open, so forms start fresh each time.
 */
export default function Modal({ open, onClose, title, children, variant = "modal" }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        // A click on the dialog element itself (not its content) is the backdrop.
        if (e.target === ref.current) onClose();
      }}
      className={`${SHELL[variant]} overflow-y-auto border border-card-border bg-app-bg p-0 text-text-primary backdrop:bg-black/60`}
    >
      {open && (
        <div className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 id={titleId} className="text-lg font-bold">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary outline-none hover:bg-accent/10 hover:text-text-primary focus-visible:ring-2 focus-visible:ring-accent"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}
