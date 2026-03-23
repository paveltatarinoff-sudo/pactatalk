"use client";

import { useState, FormEvent } from "react";

type State = "idle" | "loading" | "success" | "error" | "duplicate";

export default function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [honeypot, setHoneypot] = useState(""); // anti-spam
  const [state, setState] = useState<State>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!agreed) return;

    setState("loading");

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          website: honeypot, // honeypot field
          referrer: document.referrer,
          utm_source: new URLSearchParams(window.location.search).get("utm_source"),
          utm_medium: new URLSearchParams(window.location.search).get("utm_medium"),
          utm_campaign: new URLSearchParams(window.location.search).get("utm_campaign"),
        }),
      });

      const data = await res.json();

      if (res.status === 409) {
        setState("duplicate");
        return;
      }

      if (!res.ok) {
        setErrorMsg(
          data.error === "storage_not_configured"
            ? "Хранилище не настроено. Пожалуйста, свяжитесь с нами напрямую."
            : data.message || "Что-то пошло не так. Попробуйте позже."
        );
        setState("error");
        return;
      }

      setState("success");
    } catch {
      setErrorMsg("Ошибка сети. Проверьте соединение и попробуйте ещё раз.");
      setState("error");
    }
  };

  return (
    <section id="waitlist" className="py-20 px-4 bg-indigo-50">
      <div className="max-w-md mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">
            Записаться на закрытое бета-тестирование
          </h2>
          <p className="text-slate-500 text-sm">
            Ограниченное количество мест. Пришлём доступ, как только откроем следующую группу.
          </p>
        </div>

        {state === "success" ? (
          <div className="bg-white rounded-2xl p-8 text-center border border-green-100 shadow-sm">
            <div className="text-4xl mb-3">✅</div>
            <h3 className="font-semibold text-slate-900 mb-2">Вы в списке!</h3>
            <p className="text-slate-500 text-sm">
              Мы напишем на <strong>{email}</strong>, когда откроется доступ.
            </p>
          </div>
        ) : state === "duplicate" ? (
          <div className="bg-white rounded-2xl p-8 text-center border border-amber-100 shadow-sm">
            <div className="text-4xl mb-3">👋</div>
            <h3 className="font-semibold text-slate-900 mb-2">Вы уже в списке</h3>
            <p className="text-slate-500 text-sm">
              Этот email уже зарегистрирован. Мы напишем, когда откроется доступ.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl p-6 shadow-sm border border-indigo-100">
            {/* Honeypot — скрытое поле, боты заполняют его */}
            <input
              type="text"
              name="website"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
              style={{ display: "none" }}
              tabIndex={-1}
              autoComplete="off"
            />

            <div className="mb-4">
              <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition"
              />
            </div>

            <div className="mb-5">
              <label className="flex gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  required
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-indigo-600 flex-shrink-0"
                />
                <span className="text-sm text-slate-500 leading-relaxed">
                  Я согласен(а) получать уведомления о запуске и понимаю, что GCS-45 не является медицинской или терапевтической услугой
                </span>
              </label>
            </div>

            {state === "error" && (
              <div className="mb-4 bg-red-50 text-red-600 text-sm px-4 py-3 rounded-xl border border-red-100">
                {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={state === "loading" || !agreed}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-300 text-white font-semibold py-3.5 rounded-xl transition-colors"
            >
              {state === "loading" ? "Отправляем..." : "Записаться на ЗБТ"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}
