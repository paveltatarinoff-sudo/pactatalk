const cards = [
  {
    icon: "💬",
    title: "Когда разговор заходит в тупик",
    desc: "Одна и та же тема по кругу, и никто не чувствует, что его услышали.",
  },
  {
    icon: "📅",
    title: "Когда нужно принять совместное решение",
    desc: "Переезд, деньги, дети, работа — темы, где у каждого своя позиция.",
  },
  {
    icon: "🧩",
    title: "Когда накопилось напряжение",
    desc: "Ничего острого, но что-то висит в воздухе уже давно.",
  },
  {
    icon: "🕐",
    title: "Когда нет времени на долгий процесс",
    desc: "Вы хотите разобраться здесь и сейчас, а не ждать месяцами.",
  },
];

export default function ForWhom() {
  return (
    <section className="py-20 px-4 bg-white">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 text-center mb-3">
          Для кого
        </h2>
        <p className="text-slate-500 text-center mb-12 max-w-xl mx-auto">
          GCS-45 подходит парам, которые хотят поговорить по-настоящему — структурированно и без обвинений.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {cards.map((card) => (
            <div
              key={card.title}
              className="border border-slate-100 rounded-2xl p-6 bg-slate-50 hover:bg-white hover:shadow-sm transition-all"
            >
              <div className="text-3xl mb-3">{card.icon}</div>
              <h3 className="font-semibold text-slate-900 mb-1.5">{card.title}</h3>
              <p className="text-slate-500 text-sm leading-relaxed">{card.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
