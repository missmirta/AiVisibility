<!doctype html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title', 'AI Visibility')</title>
    <style>
        :root {
            --bg: #fafaf8; --fg: #1d1d1b; --muted: #6b6b66; --line: #e2e1db; --card: #fff;
            --accent: #2f5d8a; --accent-soft: #bcd0e4; --warn-bg: #fff4d6; --warn-fg: #6a4e00;
            --pos: #2f6f4f; --neg: #a0412d;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #161614; --fg: #ecebe6; --muted: #9a998f; --line: #34332f; --card: #1e1e1b;
                --accent: #7fb0e0; --accent-soft: #34506b; --warn-bg: #3a3112; --warn-fg: #f1d98a;
                --pos: #6fc79a; --neg: #e48a76;
            }
        }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; }
        header, main, footer { max-width: 1040px; margin: 0 auto; padding: 0 16px; }
        header { padding-top: 20px; }
        h1 { font-size: 22px; margin: 0 0 4px; }
        h2 { font-size: 18px; margin: 28px 0 8px; }
        nav { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 12px 0 8px; border-bottom: 1px solid var(--line); }
        nav a { color: var(--muted); text-decoration: none; padding: 6px 0; border-bottom: 2px solid transparent; }
        nav a.active { color: var(--fg); border-color: var(--accent); }
        nav a.highlight { margin-left: auto; align-self: center; margin-bottom: 4px; padding: 5px 14px; font-weight: 600;
            color: var(--bg); background: var(--accent); border: 2px solid var(--accent); border-radius: 999px; }
        nav a.highlight:hover { filter: brightness(1.1); }
        nav a.highlight.active { box-shadow: 0 0 0 3px var(--accent-soft); }
        .lead, .muted { color: var(--muted); }
        .note { background: var(--warn-bg); color: var(--warn-fg); padding: 10px 12px; border-radius: 6px; margin: 12px 0; }
        .scroll { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; background: var(--card); }
        th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
        th { font-weight: 600; font-size: 13px; color: var(--muted); }
        td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .bar { position: relative; height: 14px; min-width: 160px; background: var(--line); border-radius: 3px; }
        .bar .ci { position: absolute; top: 4px; height: 6px; background: var(--accent-soft); border-radius: 3px; }
        .bar .pt { position: absolute; top: 0; width: 3px; height: 14px; background: var(--accent); }
        .own { color: var(--muted); font-style: italic; }
        .cell { text-align: center; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .cell small { display: block; color: var(--muted); font-size: 11px; }
        footer { padding: 28px 16px 40px; color: var(--muted); font-size: 13px; }
        svg text { fill: var(--muted); font-size: 11px; }
        .legend span { margin-right: 16px; }
        .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
    </style>
</head>
<body>
<header>
    <h1>AI Visibility</h1>
    <div class="lead">Як AI-асистенти згадують бренди — кожна оцінка з довірчим інтервалом</div>
    <nav>
        <a href="{{ route('methodology') }}" @class(['active' => request()->routeIs('methodology')])>Методологія й обмеження</a>
        <a href="{{ route('overview') }}" @class(['active' => request()->routeIs('overview')])>Видимість брендів</a>
        <a href="{{ route('convergence') }}" @class(['active' => request()->routeIs('convergence')])>Збіжність</a>
        <a href="{{ route('perception') }}" @class(['active' => request()->routeIs('perception')])>Карта сприйняття</a>
        <a href="{{ route('representativeness') }}" @class(['active' => request()->routeIs('representativeness')])>Репрезентативність</a>
        <a href="{{ route('adaptive') }}" @class(['active' => request()->routeIs('adaptive')])>Адаптивний семплінг</a>
        <a href="{{ route('stance') }}" @class(['active' => request()->routeIs('stance')])>Тональність</a>
        <a href="{{ route('model') }}" @class(['active' => request()->routeIs('model')])>Власна модель</a>
        <a href="{{ route('conclusions') }}" @class(['highlight', 'active' => request()->routeIs('conclusions')])>Висновки →</a>
    </nav>
</header>
<main>
    @yield('content')
</main>
<footer>
    @isset($meta)
        Дані: {{ $meta['generated_at'] ?? '?' }} · git {{ $meta['git_sha'] ?? '?' }} · seed {{ $meta['seed'] ?? '?' }}
        · моделі: {{ collect($meta['models'] ?? [])->map(fn ($m, $e) => "$e = $m")->implode(', ') }}
        @if (! empty($meta['not_exported']))
            <br>Ще не експортовано: {{ implode(', ', $meta['not_exported']) }}
        @endif
    @endisset
</footer>
</body>
</html>
