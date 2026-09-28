# AiVisibility

## Методологія: скільки запитів потрібно на движок

Довірчий інтервал mention rate конкурента звужується зі зростанням n
приблизно за формою `1/sqrt(n)`. На наявних даних пілоту (Stripe/Paddle,
2 бренди) ціль ±5 в.п. ще не досягається: на n=36 (Claude) ширина CI ≈7.6
в.п., на n=24 (OpenAI) — теж ≈7.6 в.п. Екстраполяція форми кривої дає
орієнтир ≈84 запити на движок для Claude і ≈46 для OpenAI. Це **емпіричний
орієнтир для нашого сетапу** (ці два бренди, fintech-ніша, ці движки), а
не універсальна формула мінімального розміру вибірки — таку строгу
параметричну формулу автор методології (Sielinski, arXiv:2603.08924) сам
залишив окремою майбутньою роботою. Деталі методу й повний вивід —
`docs/weeks/week4.md`.

## Посилання

- [New Research: AIs Are Highly Inconsistent When Recommending Brands or Products](https://sparktoro.com/blog/new-research-ais-are-highly-inconsistent-when-recommending-brands-or-products-marketers-should-take-care-when-tracking-ai-visibility/)
