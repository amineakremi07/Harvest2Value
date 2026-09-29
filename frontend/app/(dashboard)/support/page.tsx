import { BookOpen, Mail, Phone } from "lucide-react";
import PageTitle from "@/app/components/PageTitle";
import { glassCard } from "@/app/components/styles";

const FAQ = [
  {
    q: "How is the Δ Income and Δ Waste badge calculated?",
    a: "Each badge compares the current period with the most recent previous one: (current − previous) ÷ previous × 100. Income going up is good; waste going down is good, so the colour shows good or bad while the arrow shows direction.",
  },
  {
    q: "How do I register a farmer with several crops?",
    a: "Open Farmers, choose Add Farmer, then use Add crop for each crop the farmer harvested. Enter yield, waste and income per crop, plus the farmer's storage capacity.",
  },
  {
    q: "What does the Regional Risk Score mean?",
    a: "It is a 0–100 indicator that drops as the share of harvest wasted grows and as storage fills above 75%. It is a placeholder formula until the analytics engine defines the official one.",
  },
  {
    q: "Why are some numbers marked as sample data?",
    a: "Farmers, facilities, weather and sensor readings are sample data until the regional database endpoints are connected.",
  },
];

const DOCS = ["Getting started for CRDA agents", "Recording harvests and storage", "Reading analytics and trends", "Using the AI assistant"];

export default function SupportPage() {
  return (
    <>
      <PageTitle title="Help & Support" subtitle="Platform documentation, answers to common questions, and contact details." />

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-labelledby="faq-title" className={`${glassCard} lg:col-span-2`}>
          <h2 id="faq-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Frequently asked questions
          </h2>
          <div className="divide-y divide-card-border">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-3">
                <summary className="cursor-pointer list-none rounded-lg text-sm font-semibold text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-accent">
                  {item.q}
                </summary>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <div className="space-y-4">
          <section aria-labelledby="docs-title" className={glassCard}>
            <h2 id="docs-title" className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-text-secondary">
              <BookOpen className="h-4 w-4" aria-hidden="true" /> Documentation
            </h2>
            <ul className="space-y-2 text-sm text-text-primary">
              {DOCS.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-text-secondary">Guides are being written and will be linked here.</p>
          </section>

          <section aria-labelledby="contact-title" className={glassCard}>
            <h2 id="contact-title" className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
              Contact support
            </h2>
            <ul className="space-y-2 text-sm text-text-primary">
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-accent-text" aria-hidden="true" />
                <span className="font-mono">support@crda.example</span>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-accent-text" aria-hidden="true" />
                <span className="font-mono">+216 00 000 000</span>
              </li>
            </ul>
            <p className="mt-3 text-xs text-text-secondary">Placeholder contact details — replace with the CRDA helpdesk.</p>
          </section>
        </div>
      </div>
    </>
  );
}
