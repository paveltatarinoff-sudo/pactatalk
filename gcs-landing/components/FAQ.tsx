"use client";

import { useState } from "react";

const faqs = [
  {
    q: "Нужно ли нам обоим участвовать одновременно?",
    a: "Да, сессия проходит вместе — оба партнёра должны быть в одном месте (или рядом). Бот ведёт диалог по очереди с каждым.",
  },
  {
    q: "Что если один из нас не хочет участвовать?",
    a: "GCS-45 работает только при добровольном участии обоих. Если один из партнёров не готов — сессию лучше отложить.",
  },
  {
    q: "Это терапия? Нужен ли специалист?",
    a: "Нет, это не терапия и не замена психолога. GCS-45 — инструмент для структурированного разговора. Если ситуация требует профессиональной помощи, бот сообщит об этом и направит к специалисту.",
  },
  {
    q: "Сохраняется ли содержание нашего разговора?",
    a: "По умолчанию содержимое сессии минимально. В режиме «не сохранять» переписка не хранится на серверах после завершения сессии. Мы сохраняем только технические метаданные.",
  },
  {
    q: "Можно ли остановить сессию в любой момент?",
    a: "Да. Любой из участников может остановить сессию командой в любой момент. Никаких обязательств по её завершению нет.",
  },
  {
    q: "Что происходит, если возникает конфликт или риск?",
    a: "Если бот обнаруживает признаки острого кризиса или риска, он останавливает сессию (Stop&Route) и предлагает обратиться к живому специалисту.",
  },
  {
    q: "На каком языке проходит сессия?",
    a: "В бета-версии поддерживается русский язык. Поддержка других языков — в планах.",
  },
  {
    q: "Сколько стоит?",
    a: "Закрытое бета-тестирование — бесплатно для участников. Ценообразование будет определено после бета-периода на основе обратной связи.",
  },
];

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section className="py-20 px-4 bg-white">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 text-center mb-12">
          Частые вопросы
        </h2>
        <div className="space-y-2">
          {faqs.map((faq, i) => (
            <div key={i} className="border border-slate-100 rounded-xl overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full text-left px-5 py-4 flex justify-between items-center gap-4 hover:bg-slate-50 transition-colors"
              >
                <span className="font-medium text-slate-900 text-sm md:text-base">
                  {faq.q}
                </span>
                <span className="text-slate-400 text-xl flex-shrink-0">
                  {open === i ? "−" : "+"}
                </span>
              </button>
              {open === i && (
                <div className="px-5 pb-4 text-slate-500 text-sm leading-relaxed border-t border-slate-100 pt-3">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
