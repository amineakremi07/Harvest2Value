import { Search } from "lucide-react";

export default function Header() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#1E293B] bg-[#090D16] px-2 py-4">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-400">
          Allocate your harvest across buyers and storage to maximize net profit.
        </p>
      </div>

      
    </header>
  );
}
