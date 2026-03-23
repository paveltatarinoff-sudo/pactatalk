"use client";

export default function Hero() {
  const scrollToForm = () => {
    document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToHow = () => {
    document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className="bg-slate-900 text-white py-24 px-4">
      <div className="max-w-3xl mx-auto text-center">
        <div className="inline-block bg-indigo-500/20 text-indigo-300 text-sm font-medium px-4 py-1.5 rounded-full mb-6 border border-indigo-500/30">
          Закрытое бета-тестирование — заявки открыты
        </div>

        <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-6 tracking-tight">
          Структурированный разговор<br className="hidden md:block" /> для пары —
          без посредников
        </h1>

        <p className="text-lg md:text-xl text-slate-300 mb-4 max-w-2xl mx-auto leading-relaxed">
          GCS-45 — это 45-минутная сессия в Telegram, где нейтральный AI задаёт вопросы по очереди каждому из вас, помогая дойти до 1–2 конкретных договорённостей.
        </p>
        <p className="text-sm text-slate-400 mb-10">
          Не терапия. Не советы. Только структура и ваши слова.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={scrollToForm}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-colors text-base"
          >
            Записаться на ЗБТ
          </button>
          <button
            onClick={scrollToHow}
            className="border border-slate-600 hover:border-slate-400 text-slate-300 hover:text-white font-medium px-8 py-3.5 rounded-xl transition-colors text-base"
          >
            Как проходит сессия →
          </button>
        </div>
      </div>
    </section>
  );
}
