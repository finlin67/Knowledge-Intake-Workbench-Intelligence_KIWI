'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'

type Tab = 'Quick Start' | 'FAQ' | 'Glossary'

const quickStartSteps = [
  {
    title: 'Step 1 — Project Setup',
    body: 'On the Home screen, enter a Project Name, Export Folder name, and choose your Export Profile (AnythingLLM, Open WebUI, or Both). Click Save Project. You only do this once — all settings persist across every batch you run.'
  },
  {
    title: 'Step 2 — Scan a Batch',
    body: 'Enter your batch folder name in the Import Folder field (example: batch_001). Click Scan Batch. KIWI will read all files in that folder and add them to the queue. You will see a file count update on the right side of the screen.'
  },
  {
    title: 'Step 3 — Check Settings (optional but recommended)',
    body: 'Before your first run, click Settings in the top navigation. Review your AI Provider (Ollama, Claude, or OpenAI), confirm your Workspaces match your document types, and check your Keywords rules. You can skip this and use rules-only mode with no AI model required.'
  },
  {
    title: 'Step 4 — Run the Batch',
    body: 'Click Run Batch in the right panel. KIWI will classify, normalize, chunk, and export each file. Watch the file count in the queue decrease as files are processed. Before running, check Triage for any files marked as unassigned that may need manual workspace assignment.'
  },
  {
    title: 'Step 5 — Start the Next Batch',
    body: 'After the run completes, click Start Next Batch. This clears only the current batch folder field — your project name, export folder, export profile, and all settings stay saved. Enter batch_002 in the batch folder field, click Scan Batch, and click Run Batch. Repeat until all batches are complete.'
  }
]

const faqItems = [
  {
    question: 'What file types does KIWI support?',
    answer: 'Best results with .md, .txt, .docx, .pdf, .pptx. Images, audio, and video are not supported.'
  },
  {
    question: 'Why are my files showing as "unassigned"?',
    answer:
      "KIWI classifies files using your classification rules. If a file doesn't match any rule it lands in unassigned. Go to Settings → My Categories to add keywords and workspaces that match your files. Then re-scan and run again."
  },
  {
    question: 'How many files can I process at once?',
    answer:
      'We recommend batches of 300-500 files. Use the Batch Files tool (coming soon) to split larger folders. Larger batches may be slow but will still complete.'
  },
  {
    question: 'What is the difference between AnythingLLM and Open WebUI?',
    answer:
      'These are two different local AI tools that use your documents. AnythingLLM: desktop app, drag-and-drop document upload. Open WebUI: browser-based, more customizable. Select Both if you use either or are unsure.'
  },
  {
    question: 'Where are my exported files?',
    answer:
      'In your export folder under: exports/anythingllm/ — for AnythingLLM, exports/open_webui/ — for Open WebUI. Each workspace becomes a subfolder.'
  },
  {
    question: 'The Run Batch button does nothing. What is wrong?',
    answer:
      'Most likely the backend is not running. Check that the Backend: Online badge shows green on the Home/Setup screen. If it shows red, run start_kiwi.bat again. Also make sure Step 2 scan succeeded first — Run Batch appears only after scanning.'
  },
  {
    question: 'Can I stop and resume a run?',
    answer:
      'Yes. KIWI saves progress after each file. If you close the app mid-run, reopen it, reload your project, and click Run Batch again. Already-processed files will be skipped automatically.'
  }
]

const glossaryItems = [
  {
    term: 'Workspace',
    definition: 'A category folder that groups related documents together. Example: career_portfolio, ai_projects, archive'
  },
  {
    term: 'Batch',
    definition: 'A folder containing a subset of your files (recommended: 300-500 files). Use batches to avoid overloading the tool on large archives.'
  },
  {
    term: 'Scan',
    definition: 'The step where KIWI reads your files and adds them to the processing queue.'
  },
  {
    term: 'Queue',
    definition: 'The list of files waiting to be processed.'
  },
  {
    term: 'Triage',
    definition: 'A review step where you manually assign files that KIWI could not automatically classify.'
  },
  {
    term: 'Run',
    definition: 'The full processing pipeline: classify → normalize → chunk → export.'
  },
  {
    term: 'Classification Rules',
    definition:
      'Instructions in classification_rules.json that tell KIWI how to route files based on filename keywords and content patterns.'
  },
  {
    term: 'Export Profile',
    definition: 'The format KIWI uses for output files. AnythingLLM and Open WebUI require slightly different formats.'
  },
  {
    term: 'Session',
    definition:
      'KIWI tracks your active project with a session token. If you see errors, try reloading your project from the Home screen.'
  }
]

export default function HelpPage() {
  const [tab, setTab] = useState<Tab>('Quick Start')
  const [open, setOpen] = useState<number | null>(null)

  return (
    <div className="mx-auto max-w-6xl space-y-6 bg-[var(--kiwi-bg)] px-2 md:px-4">
      <PageHeader title="Help & Documentation" subtitle="A simple guide for getting started with KIWI" />

      <div className="flex border-b border-[var(--kiwi-border)]">
        {(['Quick Start', 'FAQ', 'Glossary'] as const).map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === item
                ? 'border-b-2 border-[var(--kiwi-blue)] text-[var(--kiwi-text)]'
                : 'text-[var(--kiwi-text-2)] hover:text-[var(--kiwi-text)]'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === 'Quick Start' ? (
        <div className="space-y-4">
          <div className="relative">
            <div className="absolute left-0 right-0 top-5 hidden h-0.5 bg-[var(--kiwi-border)] md:block" />
            <div className="grid gap-4 md:grid-cols-5">
              {quickStartSteps.map((step, idx) => (
                <div
                  key={step.title}
                  className="relative rounded-xl border border-[var(--kiwi-border)] bg-white p-4 shadow-sm"
                >
                  <div className="mb-3 flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--kiwi-blue)] text-base font-bold text-white">
                      {idx + 1}
                    </div>
                    <h3 className="text-sm font-bold text-[var(--kiwi-text)]">{step.title}</h3>
                  </div>
                  <p className="text-sm leading-relaxed text-[var(--kiwi-text-2)]">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {tab === 'FAQ' ? (
        <div className="space-y-3">
          {faqItems.map((item, idx) => (
            <div key={item.question} className="overflow-hidden rounded-xl border border-[var(--kiwi-border)] bg-white shadow-sm">
              <button
                onClick={() => setOpen(open === idx ? null : idx)}
                className="flex w-full items-center justify-between px-5 py-4 text-left"
              >
                <span className="pr-4 text-sm font-semibold text-[var(--kiwi-text)]">Q: {item.question}</span>
                <ChevronDown
                  className={`h-4 w-4 shrink-0 text-[var(--kiwi-text-2)] transition-transform duration-300 ${
                    open === idx ? 'rotate-180' : ''
                  }`}
                />
              </button>
              <div
                className={`overflow-hidden px-5 text-sm leading-relaxed text-[var(--kiwi-text-2)] transition-all duration-300 ${
                  open === idx ? 'max-h-96 pb-4' : 'max-h-0'
                }`}
              >
                <p>A: {item.answer}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {tab === 'Glossary' ? (
        <div className="rounded-xl border border-[var(--kiwi-border)] bg-white p-5 shadow-sm">
          <dl className="space-y-4">
            {glossaryItems.map((item) => (
              <div key={item.term}>
                <dt className="font-semibold text-[var(--kiwi-text)]">{item.term} —</dt>
                <dd className="ml-4 text-sm leading-relaxed text-[var(--kiwi-text-2)]">{item.definition}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </div>
  )
}
