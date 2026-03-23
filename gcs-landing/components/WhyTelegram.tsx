const features = [
  {
    icon: "📱",
    title: "Там, где вы уже есть",
    desc: "Не нужно скачивать новое приложение. Telegram есть у большинства — просто открываете бота.",
  },
  {
    icon: "✍️",
    title: "Текст или голосовые",
    desc: "Можно печатать, можно отвечать голосовым сообщением — как удобнее в данный момент.",
  },
  {
    icon: "⏸️",
    title: "Можно делать паузы",
    desc: "Сессия не прерывается, если нужно время подумать. Никакого давления на скорость ответа.",
  },
  {
    icon: "🔒",
    title: "Приватно по умолчанию",
    desc: "Бот не видит историю других переписок. Сессия — это отдельное пространство.",
  },
];

export default function WhyTelegram() {
  return (
    <section className="py-20 px-4 bg-white">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 text-center mb-3">
          Почему Telegram-бот
        </h2>
        <p className="text-slate-500 text-center mb-12 max-w-xl mx-auto">
          Никаких видеозвонков и незнакомых кабинетов. Разговор — в привычном мессенджере.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {features.map((f) => (
            <div key={f.title} className="flex gap-4 p-5 rounded-2xl border border-slate-100 bg-slate-50">
              <div className="text-2xl">{f.icon}</div>
              <div>
                <h3 className="font-semibold text-slate-900 mb-1">{f.title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
