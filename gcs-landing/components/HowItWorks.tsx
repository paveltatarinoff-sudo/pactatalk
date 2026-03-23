const steps = [
  {
    num: "01",
    title: "Контракт и цель",
    desc: "Оба участника соглашаются с правилами сессии и называют тему, которую хотят разобрать. AI фиксирует цель.",
    duration: "~5 мин",
  },
  {
    num: "02",
    title: "Позиции по очереди",
    desc: "Каждый по очереди отвечает на вопросы AI. Пока один говорит — другой слушает. AI не перебивает и не оценивает.",
    duration: "~10 мин",
  },
  {
    num: "03",
    title: "Mirroring",
    desc: "AI просит каждого своими словами пересказать то, что сказал партнёр. Без интерпретаций — только то, что прозвучало.",
    duration: "~10 мин",
  },
  {
    num: "04",
    title: "Карта цикла и первопричины",
    desc: "AI помогает увидеть паттерн: что запускает конфликт, как он развивается, где точка входа для изменений.",
    duration: "~10 мин",
  },
  {
    num: "05",
    title: "1–2 договорённости",
    desc: "Оба формулируют конкретные, измеримые шаги. AI фиксирует договорённости и присылает итог сессии.",
    duration: "~10 мин",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 px-4 bg-slate-50">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 text-center mb-3">
          Как проходит 45-минутная сессия
        </h2>
        <p className="text-slate-500 text-center mb-12 max-w-xl mx-auto">
          Пять последовательных блоков — каждый со своей функцией.
        </p>

        <div className="space-y-4">
          {steps.map((step) => (
            <div
              key={step.num}
              className="bg-white rounded-2xl p-6 border border-slate-100 flex gap-5 items-start"
            >
              <div className="text-indigo-600 font-bold text-lg font-mono min-w-[2.5rem]">
                {step.num}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1.5">
                  <h3 className="font-semibold text-slate-900">{step.title}</h3>
                  <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
                    {step.duration}
                  </span>
                </div>
                <p className="text-slate-500 text-sm leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
