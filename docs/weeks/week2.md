# Тиждень 2 — Prober + сховище

Деталізація розділу "Тиждень 2" з `docs/ai_visibility_fintech_plan.md`.
2 робочі дні: День 1 — сховище (SQLite) + Claude Prober, День 2 — OpenAI
Prober + retry/backoff + логування вартості + заділ під cron.

Вхідні дані вже готові з Тижня 1: `data/brands/*.json` (2 підтверджені
профілі), `data/queries/queries.json` (24 запити, 2 бренди × 6 категорій).
Жодних змін у цей набір цей тиждень не вносимо — Prober тільки читає його.

## Мета тижня

Прогнати всі 24 запити через **два движки** (Claude + OpenAI) і зберегти
структурований результат (запит → прогін → відповідь) у SQLite, з логуванням
токенів/вартості й retry/backoff з першого дня. `mentions` (виявлені
згадки) — це вже Тиждень 3, тут тільки створюємо порожню таблицю-заділ під
неї.

## День 1 — Сховище (SQLite) + Claude Prober

### 1. Схема БД (`aivisibility/common/db.py`, stdlib `sqlite3` — без ORM)

Файл БД: `data/db/aivisibility.sqlite3`.

    queries    id, brand, intent, text, mentions_competitors (JSON),
               UNIQUE(brand, text)
    runs       id, started_at, notes
    responses  id, run_id FK, query_id FK, engine ('claude'|'openai'),
               model, raw_text, prompt_tokens, completion_tokens,
               cost_usd, latency_ms, error (NULL якщо ок), created_at
    mentions   id, response_id FK, brand_mentioned, method
               -- порожня в тижні 2, логіка детекції — Тиждень 3

`init_db()` створює таблиці, якщо їх нема (`CREATE TABLE IF NOT EXISTS`).
`load_queries_from_json()` — ідемпотентно завантажує `queries.json` у
таблицю `queries` (`INSERT OR IGNORE` за `UNIQUE(brand, text)`), можна
запускати повторно без дублів.

### 2. Спільний контракт проберів (`aivisibility/prober/base.py`)

`ProbeResult` (dataclass): `text, prompt_tokens, completion_tokens,
cost_usd, latency_ms, model, error`. Обидва движки (Claude, OpenAI)
повертають цю саму форму — шар збереження в БД не знає, який це движок.

Промпт для проберів — це сам запит користувача як є (без system prompt,
без інструментів/web search): ми імітуємо, що бачить звичайний користувач,
коли питає AI напряму, а не агента з доступом до пошуку. Це важливо для
чесного порівняння Claude vs OpenAI (однакові умови) і для методологічної
відповідності статті Sielinski (вимірюємо базову поведінку моделі, не
retrieval-augmented).

### 3. Claude Prober (`aivisibility/prober/claude_prober.py`)

- `async def probe(query_text: str) -> ProbeResult`
- `ClaudeAgentOptions(tools=[], model=CLAUDE_MODEL, max_budget_usd=...)` —
  модель фіксуємо явно в конфізі (не дефолт CLI), бо з цього тижня це вже
  вимірювання, а не розвідка — відтворюваність важлива.
- Токени й вартість — з `ResultMessage.usage` / `total_cost_usd` (SDK вже
  рахує, як і в Discovery/Query Generator).
- Латентність — `time.monotonic()` навколо виклику.

### Критерії готовності Дня 1

- [x] `data/db/aivisibility.sqlite3` створено, 4 таблиці існують
- [x] Усі 24 запити з `queries.json` завантажені в `queries` (повторний
      запуск завантаження не створює дублів)
- [x] Claude prober відпрацював на 1 тестовому запиті, рядок у `responses`
      має ненульові `prompt_tokens`/`completion_tokens`/`cost_usd`
- [x] Повний прогін по всіх 24 запитах через Claude створює 24 рядки в
      `responses`, прив'язані до одного `runs.id`

## День 2 — OpenAI Prober + retry/backoff + вартість + заділ під cron

### 1. Залежності й ключ

- `openai` (офіційний Python SDK)
- `.env`: `OPENAI_API_KEY=` (реальний ключ — не комітиться, вже є в
  `.gitignore`)

### 2. OpenAI Prober (`aivisibility/prober/openai_prober.py`)

- Той самий контракт `ProbeResult`.
- `client.chat.completions.create(model=OPENAI_MODEL, messages=[...])`,
  без tools/function calling.
- Модель за замовчуванням — `gpt-4o-mini` (дешево, достатньо для пілоту;
  константа в конфізі, легко замінити на `gpt-4o`, якщо якість виявиться
  замалою для змістовних відповідей).
- OpenAI API не повертає вартість напряму — рахуємо самі за
  `response.usage.prompt_tokens/completion_tokens` і невеликою таблицею
  цін за модель у конфізі (оновлювати вручну, якщо OpenAI змінить тарифи).

### 3. Retry з backoff (`aivisibility/prober/retry.py`)

Невелика власна реалізація (не окрема залежність на кшталт `tenacity` —
завдання достатньо просте): `async def with_retry(coro_factory,
max_attempts=3, base_delay=1.0)`, експоненційна затримка між спробами,
після вичерпання спроб — повертає `ProbeResult` з заповненим `error`
(не валить весь прогін через один збій запиту).

### 4. Уніфікований runner (`scripts/run_prober.py`)

- Створює один рядок у `runs` (`started_at=now`).
- Для кожного запиту з БД × кожного з 2 движків: `with_retry(probe)`,
  зберегти `responses`-рядок (успіх або помилка — обидва зберігаються).
- Друкує прогрес і накопичену вартість по кожному движку окремо й разом.
- Ідемпотентність не потрібна на рівні runner'а: кожен запуск — новий
  `run_id`, повторні спостереження — це очікувано і знадобиться для
  майбутніх "довших вікон" (про це прямо каже мастер-план у розділі
  Тиждень 2).

### 5. Заділ під cron (документація, без реального налаштування)

Скрипт `scripts/run_prober.py` вже безпечно перезапускати щодня як є.
Реальне планування (Windows Task Scheduler) — окремий крок, який робить
користувач сам, коли вирішить; я не чіпаю системний планувальник
автоматично. Приклад команди для реєстрації задачі (довідково, в
`docs/weeks/week2.md`, не виконується агентом):

    schtasks /create /tn "AiVisibility Prober" /tr "<шлях до python.exe> <шлях до run_prober.py>" /sc daily /st 09:00

### QC

- Після повного прогону: у БД рівно 48 нових рядків `responses`
  (24 запити × 2 движки) з одним `run_id`.
- Порахувати й вивести кількість помилок (`error IS NOT NULL`) і сумарну
  вартість прогону.

### Критерії готовності Дня 2

- [x] OpenAI prober відпрацював end-to-end, рядок у `responses` має
      токени/вартість/латентність
- [x] Повний прогін `scripts/run_prober.py` дає рівно 48 рядків у
      `responses` для одного `run_id`
- [x] Retry/backoff у коді присутній і покриває реальний виклик (спрацював
      природно ще на етапі тесту — OpenAI-ключ без кредитів дав 429, retry
      відпрацював 3 спроби з backoff і коректно повернув помилку)
- [x] Загальна вартість одного повного прогону виведена і виглядає
      адекватно (одиниці-десятки центів, не долари)

## Фінальний результат тижня 2

- `data/db/aivisibility.sqlite3` з реальними даними: `queries` (24),
  `runs` (≥1), `responses` (48 на прогін), порожня `mentions` (заділ під
  Тиждень 3)
- Обидва prober-и (Claude, OpenAI) з єдиним контрактом `ProbeResult`,
  retry/backoff, логуванням токенів і вартості
- `scripts/run_prober.py` — придатний для ручного або cron-запуску
- Задокументована (не виконана) команда для Windows Task Scheduler

## Відкриті питання / ризики

- Ціни OpenAI за токен захардкоджені в конфізі — оновлювати вручну при
  зміні тарифів постачальником.
- `gpt-4o-mini` — дешевий дефолт, може давати менш "змістовні" відповіді
  порівняно з тим, що реальні користувачі бачать у ChatGPT за замовчуванням;
  прийнятний компроміс для пілоту, легко змінити константою.
- Rate limits на двох движках — retry/backoff мінімізує ризик, але
  повноцінні нічні batch-прогони (Batch API) — поза скоупом тижня 2,
  залишається ризиком мастер-плану на майбутнє.
- `mentions` навмисно порожня цей тиждень — сама детекція згадок це
  Тиждень 3, не плутати зі скоупом цього тижня.
- **Claude Prober йде через Claude Agent SDK (Claude Code CLI), а не через
  чистий Anthropic Messages API.** Виміряно окремо: навіть з `tools=[]` і
  `system_prompt=""` кожен виклик несе ~4000 токенів фіксованого службового
  контексту Claude Code (перевірено прямим тестом у нейтральній директорії:
  `cache_creation_input_tokens=3982` на порожній першій виклик). Свідомий
  компроміс: безкоштовно через Claude Code Pro підписку замість окремого
  оплачуваного `ANTHROPIC_API_KEY`. Наслідок — Claude-гілка вимірювання
  теоретично може мати легке "забарвлення" персоною Claude Code, на відміну
  від OpenAI-гілки (чистий `chat.completions.create`). Якщо колись
  знадобиться повна методологічна чистота (порівнянна з підходом статті
  Sielinski) — перехід на прямий Anthropic API це проста заміна одного
  модуля (`aivisibility/prober/claude_prober.py`), без зміни решти
  архітектури.
