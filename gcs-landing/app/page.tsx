const TELEGRAM_BOT_URL = "https://t.me/PactaTalkBot";
const COUPLE_CONFLICT_IMAGE =
  "/landing/left-conflict-selected.png";
const COUPLE_RELIEF_IMAGE =
  "https://images.pexels.com/photos/10767064/pexels-photo-10767064.jpeg?cs=srgb&dl=pexels-vlada-karpovich-10767064.jpg&fm=jpg&w=1400";

const painPoints = [
  { kind: "push-pull", text: "Один напирает, второй закрывается" },
  { kind: "loop", text: "Вы снова ходите по кругу вокруг одной темы" },
  { kind: "stakes", text: "Тема слишком важная, чтобы снова сорваться в спор" },
];

const steps = [
  {
    kind: "telegram",
    title: "Открываете бота в Telegram",
    description: "Без регистрации на новой платформе и без сложного входа.",
  },
  {
    kind: "turns",
    title: "Говорите по очереди",
    description: "PACTA держит структуру разговора, когда самим это уже трудно.",
  },
  {
    kind: "clarity",
    title: "Получаете больше ясности",
    description: "Не магию, а более спокойный и понятный разговор.",
  },
];

const topics = ["Дети", "Деньги", "Дистанция", "Доверие", "Будущее", "Накопленные обиды"];

const trustPoints = [
  "Не терапия и не замена психолога",
  "Можно остановиться в любой момент",
  "Если разговор становится рискованным, бот не продолжает обычную сессию",
];

function TelegramIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="none">
      <circle cx="12" cy="12" r="12" fill="#2A7DE1" />
      <path
        d="M17.96 7.17 6.96 11.42c-.75.3-.75.73-.14.92l2.82.88 1.09 3.35c.13.35.07.49.43.49.28 0 .41-.13.56-.28l1.38-1.34 2.87 2.12c.53.29.91.14 1.04-.49L18.9 8c.2-.8-.3-1.16-.94-.83Z"
        fill="#fff"
        transform="translate(-0.6 0.1)"
      />
    </svg>
  );
}

function PainIcon({ kind }: { kind: string }) {
  if (kind === "push-pull") {
    return (
      <div className="flex h-14 w-14 items-center justify-center rounded-[1.15rem] bg-[linear-gradient(180deg,#fff3ef,#ffe5db)] shadow-[0_10px_18px_rgba(224,89,71,0.16)]">
        <svg viewBox="0 0 48 48" className="h-8 w-8" aria-hidden="true" fill="none">
          <path d="M11 13h10a5 5 0 0 1 5 5v4a5 5 0 0 1-5 5h-3l-5 4v-4h-2a5 5 0 0 1-5-5v-4a5 5 0 0 1 5-5Z" fill="#FF6A57" />
          <path d="M37 35H27a5 5 0 0 1-5-5v-4a5 5 0 0 1 5-5h3l5-4v4h2a5 5 0 0 1 5 5v4a5 5 0 0 1-5 5Z" stroke="#2F3847" strokeWidth="2.4" />
        </svg>
      </div>
    );
  }

  if (kind === "loop") {
    return (
      <div className="flex h-14 w-14 items-center justify-center rounded-[1.15rem] bg-[linear-gradient(180deg,#eef6ff,#dfefff)] shadow-[0_10px_18px_rgba(42,125,225,0.14)]">
        <svg viewBox="0 0 48 48" className="h-8 w-8" aria-hidden="true" fill="none">
          <path d="M15 18a10 10 0 0 1 17-5" stroke="#2A7DE1" strokeWidth="2.8" strokeLinecap="round" />
          <path d="m30 10 2 5-5-.6" fill="#2A7DE1" />
          <path d="M33 30a10 10 0 0 1-17 5" stroke="#2F3847" strokeWidth="2.8" strokeLinecap="round" />
          <path d="m18 38-2-5 5 .6" fill="#2F3847" />
        </svg>
      </div>
    );
  }

  return (
    <div className="flex h-14 w-14 items-center justify-center rounded-[1.15rem] bg-[linear-gradient(180deg,#fff5e8,#ffe3bf)] shadow-[0_10px_18px_rgba(224,156,71,0.16)]">
      <svg viewBox="0 0 48 48" className="h-8 w-8" aria-hidden="true" fill="none">
        <path d="M24 10 9 17v8c0 9 6.4 13.6 15 17 8.6-3.4 15-8 15-17v-8L24 10Z" fill="#FFB247" />
        <path d="M24 18v8" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
        <circle cx="24" cy="31" r="2.2" fill="#fff" />
      </svg>
    </div>
  );
}

function StepIcon({ kind }: { kind: string }) {
  if (kind === "telegram") {
    return (
      <div className="flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-[linear-gradient(180deg,#eaf4ff,#d9ebff)] shadow-[0_10px_18px_rgba(42,125,225,0.16)]">
        <TelegramIcon className="h-7 w-7" />
      </div>
    );
  }

  if (kind === "turns") {
    return (
      <div className="flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-[linear-gradient(180deg,#fff2ee,#ffe2d7)] shadow-[0_10px_18px_rgba(224,89,71,0.15)]">
        <svg viewBox="0 0 48 48" className="h-8 w-8" aria-hidden="true" fill="none">
          <circle cx="15" cy="16" r="6" fill="#FF6A57" />
          <circle cx="33" cy="31" r="6" fill="#2A7DE1" />
          <path d="M21 16h9l-3-3" stroke="#2F3847" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M27 31h-9l3 3" stroke="#2F3847" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }

  return (
    <div className="flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-[linear-gradient(180deg,#fff6ea,#ffe9c8)] shadow-[0_10px_18px_rgba(230,170,74,0.16)]">
      <svg viewBox="0 0 48 48" className="h-8 w-8" aria-hidden="true" fill="none">
        <path d="M24 11 27.1 18.9 35 22l-7.9 3.1L24 33l-3.1-7.9L13 22l7.9-3.1L24 11Z" fill="#FFB247" />
        <path d="M35 9 36.4 12.6 40 14l-3.6 1.4L35 19l-1.4-3.6L30 14l3.6-1.4L35 9Z" fill="#2A7DE1" />
      </svg>
    </div>
  );
}

function CTAButtons() {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <a
        href={TELEGRAM_BOT_URL}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center justify-center rounded-full bg-[var(--accent)] px-7 py-3.5 text-sm font-semibold text-white shadow-[0_12px_22px_rgba(224,89,71,0.18)] transition-colors hover:bg-[var(--accent-strong)] sm:min-w-[12.75rem]"
      >
        <span className="mr-2 flex h-6 w-6 items-center justify-center">
          <TelegramIcon className="h-5 w-5" />
        </span>
        Открыть в Telegram
      </a>
      <a
        href="#how-it-works"
        className="inline-flex items-center justify-center rounded-full border border-[var(--line)] bg-[#f8fbff] px-7 py-3.5 text-sm font-semibold text-[var(--foreground)] shadow-[0_12px_22px_rgba(42,125,225,0.08)] transition-colors hover:bg-white sm:min-w-[12.75rem]"
      >
        Как это работает
      </a>
    </div>
  );
}

function BrandWord() {
  return <span className="brand-mark">PACTA — AI</span>;
}

export default function Home() {
  return (
    <main className="landing-shell">
      <section className="px-4 pb-8 pt-5 md:px-6 md:pb-12 md:pt-8">
        <div className="mx-auto max-w-6xl rounded-[2rem] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(255,250,245,0.88))] px-5 py-5 md:px-8 md:py-8">
          <header className="mb-8 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div>
                <div className="font-display text-4xl font-bold tracking-[-0.06em] text-[var(--surface-strong)] md:text-5xl">
                  PACTA — AI
                </div>
                <p className="mt-1 text-sm text-[var(--muted)]">Бот для сложных разговоров в паре</p>
              </div>
            </div>
            <a
              href={TELEGRAM_BOT_URL}
              target="_blank"
              rel="noreferrer"
              className="hidden rounded-full border border-[var(--line)] bg-white px-5 py-2.5 text-sm font-semibold text-[var(--foreground)] transition-colors hover:bg-[#fff7f1] md:inline-flex md:items-center"
            >
              <span className="mr-2 flex h-6 w-6 items-center justify-center">
                <TelegramIcon className="h-5 w-5" />
              </span>
              Telegram
            </a>
          </header>

          <div className="grid gap-8 lg:grid-cols-[1fr_0.88fr] lg:items-center">
            <div className="max-w-2xl">
              <h1 className="font-display max-w-3xl text-[2.75rem] font-bold leading-[0.98] tracking-[-0.065em] text-[var(--surface-strong)] md:text-[4.6rem]">
                Когда в паре пора обсудить важное, но самим удержать разговор уже не получается
              </h1>
              <p className="mt-5 max-w-xl text-base leading-8 text-[var(--muted)] md:text-lg">
                <BrandWord /> — инструмент, который помогает парам спокойнее проходить сложные разговоры, слышать друг друга и находить следующий шаг.
              </p>
              <div className="mt-7">
                <CTAButtons />
              </div>
            </div>

            <div className="mx-auto w-full max-w-[22.5rem]">
              <div className="telegram-frame p-3">
              <div className="telegram-screen rounded-[1.4rem] p-3 text-[13px] shadow-[inset_0_1px_0_rgba(255,255,255,0.26)]">
                <div className="mb-3 flex items-center justify-between px-2 text-[11px] text-[#7c8b99]">
                  <span>9:41</span>
                  <div className="flex items-center gap-1">
                    <span>◔</span>
                    <span>◕</span>
                    <span>▮</span>
                  </div>
                </div>

                <div className="mb-4 flex items-center gap-3 rounded-[1rem] bg-[#2a7de1] px-4 py-3 text-white">
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white/16 text-lg font-bold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]">
                    P
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold">PACTA — AI</div>
                    <div className="text-[11px] text-white/75">@PactaTalkBot</div>
                  </div>
                  <div className="ml-auto text-[11px] text-white/75">online</div>
                </div>

                <div className="space-y-3 text-sm leading-6">
                  <div className="flex items-end justify-end gap-2">
                    <div className="telegram-bubble-user max-w-[72%] rounded-[1.2rem] rounded-br-md px-4 py-3">
                      Мы не можем спокойно обсудить тему детей.
                    </div>
                    <img
                      src="https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=120"
                      alt="Аватар участника"
                      className="h-8 w-8 rounded-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/92 text-sm font-bold text-[#2a7de1] shadow-[0_4px_10px_rgba(42,125,225,0.14)]">
                      P
                    </div>
                    <div className="telegram-bubble-bot max-w-[78%] rounded-[1.2rem] rounded-bl-md px-4 py-3">
                      Я помогу пройти этот разговор по очереди. Сначала поймём, что для каждого здесь самое важное.
                    </div>
                  </div>
                  <div className="flex items-end gap-2">
                    <img
                      src="https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?auto=compress&cs=tinysrgb&w=120"
                      alt="Аватар участницы"
                      className="h-8 w-8 rounded-full object-cover"
                      loading="lazy"
                    />
                    <div className="telegram-bubble-user max-w-[72%] rounded-[1.2rem] rounded-bl-md px-4 py-3">
                      Для меня это про безопасность и уверенность.
                    </div>
                  </div>
                  <div className="flex items-end justify-end gap-2">
                    <div className="telegram-bubble-user max-w-[74%] rounded-[1.2rem] rounded-br-md px-4 py-3">
                      А для меня — про то, что мы всё откладываем и отдаляемся.
                    </div>
                    <img
                      src="https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=120"
                      alt="Аватар участника"
                      className="h-8 w-8 rounded-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/92 text-sm font-bold text-[#2a7de1] shadow-[0_4px_10px_rgba(42,125,225,0.14)]">
                      P
                    </div>
                    <div className="telegram-bubble-bot max-w-[80%] rounded-[1.2rem] rounded-bl-md px-4 py-3">
                      Похоже, вы приносите в этот разговор две разные стороны одной боли. Давайте сначала аккуратно разложим их по местам.
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-2 rounded-full border border-[#d7e4f3] bg-white px-4 py-3 text-xs text-[#6c7c8f]">
                  <span className="text-base">😊</span>
                  <span className="text-base">📎</span>
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--telegram-soft)] text-[var(--telegram)]">
                    🎤
                  </span>
                  Напиши сообщение или отправь голосовое
                </div>
              </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-6 md:px-6 md:py-10">
        <div className="mx-auto max-w-6xl">
          <h2 className="font-display max-w-3xl text-3xl font-bold leading-tight tracking-[-0.05em] text-[var(--surface-strong)] md:text-5xl">
            Сложные темы редко разрешаются сами. Им нужно безопасное пространство, где можно говорить спокойно и честно.
          </h2>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {painPoints.map((item) => (
              <div key={item.text} className="section-frame rounded-[1.4rem] px-5 py-4">
                <PainIcon kind={item.kind} />
                <div className="text-base leading-7 text-[var(--surface-strong)]">{item.text}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-6 md:px-6 md:py-10">
        <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-2">
          <article className="section-frame overflow-hidden rounded-[1.75rem]">
            <img
              src={COUPLE_CONFLICT_IMAGE}
              alt="Пара переживает напряжённый разговор"
              className="h-72 w-full object-cover md:h-80"
              loading="lazy"
            />
            <div className="p-5">
              <h3 className="font-display text-2xl font-bold tracking-[-0.04em] text-[var(--surface-strong)]">
                Когда разговор не держится
              </h3>
              <p className="mt-2 text-sm leading-7 text-[var(--muted)]">
                Один давит, второй закрывается, и тема становится тяжелее с каждым новым заходом.
              </p>
            </div>
          </article>

          <article className="section-frame overflow-hidden rounded-[1.75rem]">
            <img
              src={COUPLE_RELIEF_IMAGE}
              alt="Пара чувствует близость и облегчение"
              className="h-72 w-full object-cover md:h-80"
              loading="lazy"
            />
            <div className="p-5">
              <h3 className="font-display text-2xl font-bold tracking-[-0.04em] text-[var(--surface-strong)]">
                Когда появляется шанс договориться
              </h3>
              <p className="mt-2 text-sm leading-7 text-[var(--muted)]">
                PACTA не обещает магию, но помогает дойти до более ясного и живого разговора.
              </p>
            </div>
          </article>
        </div>
      </section>

      <section id="how-it-works" className="px-4 py-6 md:px-6 md:py-10">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-4 md:grid-cols-3">
            {steps.map((step, index) => (
              <article key={step.title} className="section-frame rounded-[1.5rem] p-5">
                <StepIcon kind={step.kind} />
                <div className="mb-3 text-sm font-semibold text-[var(--accent)]">0{index + 1}</div>
                <h3 className="mb-2 text-xl font-semibold text-[var(--surface-strong)]">{step.title}</h3>
                <p className="text-sm leading-7 text-[var(--muted)]">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-6 md:px-6 md:py-10">
        <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[1fr_0.95fr]">
          <div className="section-frame rounded-[1.75rem] p-6 md:p-8">
            <h2 className="font-display text-3xl font-bold leading-tight tracking-[-0.05em] text-[var(--surface-strong)] md:text-5xl">
              Темы, с которыми чаще всего приходят
            </h2>
            <div className="mt-6 flex flex-wrap gap-2.5">
              {topics.map((topic) => (
                <span
                  key={topic}
                  className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium text-[var(--surface-strong)]"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>

          <div className="section-frame rounded-[1.75rem] p-6 md:p-8">
            <h2 className="font-display text-3xl font-bold leading-tight tracking-[-0.05em] text-[var(--surface-strong)]">
              Важно понимать
            </h2>
            <ul className="mt-5 space-y-3">
              {trustPoints.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-7 text-[var(--muted)] md:text-base">
                  <span className="mt-2 h-2 w-2 rounded-full bg-[var(--accent)]" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="px-4 pb-10 pt-6 md:px-6 md:pb-14 md:pt-10">
        <div className="mx-auto max-w-6xl rounded-[2rem] bg-[linear-gradient(135deg,#d94841,#b83731)] px-6 py-10 text-white shadow-[0_24px_80px_rgba(171,47,39,0.16)] md:px-8 md:py-12">
          <div className="max-w-3xl">
            <h2 className="font-display text-4xl font-bold leading-[0.98] tracking-[-0.06em] md:text-6xl">
              Если у вас есть разговор, который вы всё откладываете, начните его в <BrandWord />
            </h2>
            <p className="mt-5 max-w-2xl text-base leading-8 text-[#ffe5db] md:text-lg">
              Без долгой подготовки. Без лишнего давления. Просто зайдите в Telegram и начните.
            </p>
            <div className="mt-7">
              <a
                href={TELEGRAM_BOT_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center rounded-full bg-white px-7 py-3.5 text-sm font-semibold text-[#a32e29] transition-colors hover:bg-[#fff4ef]"
              >
                Перейти в Telegram
              </a>
            </div>
          </div>
        </div>
      </section>

      <footer className="px-4 pb-8 text-center text-xs text-[var(--muted)] md:px-6">
        © {new Date().getFullYear()} PACTA — AI. Не является медицинской или психотерапевтической услугой.
      </footer>
    </main>
  );
}
