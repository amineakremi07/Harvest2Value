import ThemeToggle from "@/app/components/ThemeToggle";

export default function Header() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#090D16] px-2 py-4">
      <div>
        <h1 className="text-xl font-bold text-[#0F172A] dark:text-white">Dashboard</h1>
        <p className="text-sm text-[#64748B] dark:text-slate-400">
          Allocate your harvest across buyers and storage to maximize net profit.
        </p>
      </div>

      <ThemeToggle />
    </header>
  );
}
