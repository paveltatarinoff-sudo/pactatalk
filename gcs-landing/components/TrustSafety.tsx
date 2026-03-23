const items = [
  {
    icon: "⚖️",
    title: "Нейтральный AI-фасилитатор",
    desc: "AI не выбирает сторону, не даёт советов и не интерпретирует слова. Только вопросы и структура — решения принимаете вы.",
  },
  {
    icon: "🚫",
    title: "Это не терапия",
    desc: "GCS-45 — инструмент для структурированного разговора, а не психологическая помощь. При серьёзных ситуациях (насилие, кризис) бот направит к специалистам (Stop&Route).",
  },
  {
    icon: "🔐",
    title: "Минимизация данных",
    desc: "Мы храним только необходимое. Режим «не сохранять» позволяет провести сессию без хранения содержимого на серверах.",
  },
  {
    icon: "👥",
    title: "Очередность и равенство",
    desc: "У каждого партнёра равное время и равные вопросы. AI следит за очерёдностью — никто не перебивает.",
  },
];

export default function TrustSafety() {
  return (
    <section className="py-20 px-4 bg-slate-900 text-white">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-2xl md:text-3xl font-bold mb-3">Безопасность и нейтральность</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Мы думали о том, что важно для чувствительного разговора.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {items.map((item) => (
            <div
              key={item.title}
              className="bg-slate-800 rounded-2xl p-6 border border-slate-700"
            >
              <div className="text-2xl mb-3">{item.icon}</div>
              <h3 className="font-semibold text-white mb-2">{item.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
