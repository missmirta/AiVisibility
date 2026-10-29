@extends('layouts.app')
@section('title', 'Тональність')
@section('content')
    <h2>Як саме згадують бренди</h2>
    @if (! ($stance['available'] ?? false))
        <div class="note">Немає даних про тональність (потрібні мітки в <code>data/labels/stance.csv</code>).</div>
    @else
        @php
            $names = ['recommended' => 'рекомендує', 'neutral' => 'нейтрально', 'negative' => 'негативно'];
            $colors = ['recommended' => 'var(--pos)', 'neutral' => 'var(--accent-soft)', 'negative' => 'var(--neg)'];
            $pct = fn ($x) => round($x * 100);
            $agree = $stance['teacher_agreement'] ?? ['available' => false];
        @endphp
        <p class="muted">Частка сніпетів (речення навколо згадки бренду) за тональністю. У дужках — 95% CI
            (bootstrap по відповідях, бо сніпети однієї відповіді залежні). Групи з однієї відповіді не мають CI.
            Всього сніпетів: {{ $stance['n_snippets'] }}.</p>

        <div class="note">Мітки поставив Claude, а не людина.
            @if ($agree['available'] ?? false)
                На {{ $agree['n'] }} сніпетах, розмічених людиною, узгодженість людини й Claude: Cohen's κ =
                {{ number_format($agree['kappa'], 2) }}
                [{{ number_format($agree['kappa_ci_low'], 2) }}–{{ number_format($agree['kappa_ci_high'], 2) }}].
            @else
                Порівняння з людською розміткою недоступне.
            @endif
            Слабкі порівняльні критики («менш функціональний, ніж X») часто йдуть як «нейтрально», тож частку
            негативних, найімовірніше, занижено.</div>

        <details>
            <summary>Власна модель-студент: чому її тут немає і яка в неї якість</summary>
            <p>Окрім міток Claude, у проєкті навчено дешеву модель-«студента», яка вчиться на цих мітках, щоб
                розмічати нові відповіді безкоштовно. Цифри в таблицях нижче — <b>лише з міток Claude</b>: усі
                {{ $stance['n_snippets'] }} сніпети вже ним розмічені, тож студент до них нічого не додає.</p>
            <p>Якість студента перевірено на золотому наборі: 120 сніпетів, розмічених людиною
                (знімок від 2026-10-12, документація <code>docs/stance_classifier.md</code>).</p>
            <div class="scroll">
            <table>
                <thead><tr><th>Модель</th><th class="num">Macro-F1 на золотому наборі</th>
                    <th class="num">Recall «негативно»</th></tr></thead>
                <tbody>
                <tr><td>TF-IDF + логістична регресія</td><td class="num">0.43</td><td class="num">0.14</td></tr>
                <tr><td>Ембединги (bge-small) + логістична регресія</td><td class="num">0.46</td><td class="num">0.14</td></tr>
                <tr><td>Fine-tuned distilroberta-base (4 зерна)</td><td class="num">0.53–0.62 (середнє 0.58)</td>
                    <td class="num">0.32–0.43 (середнє 0.39)</td></tr>
                </tbody>
            </table>
            </div>
            <ul>
                <li><b>Macro-F1</b> — середня якість по трьох класах («рекомендує», «нейтрально», «негативно»), від 0 до
                    1. <b>Recall «негативно»</b> — яку частку справжніх негативів модель знайшла.</li>
                <li>Слабке місце — м'які порівняльні негативи («менш функціональний, ніж X») модель вважає
                    нейтральними. Точність для «негативно» висока (≈0.78), а повнота низька: студент пропускає
                    більшість негативів.</li>
                <li>Лише зерно (seed) зсуває якість fine-tuned моделі приблизно на 9 пунктів, тож одному запуску
                    довіряти не можна.</li>
                <li>Висновок: студент поки гірший за вчителя і замінити Claude не може, тому дашборд використовує мітки
                    Claude. Це знімок на дату вище; після нового навчання цифри треба оновити вручну.</li>
            </ul>
        </details>

        <details>
            <summary>Що таке Cohen's κ</summary>
            <p>Cohen's κ («каппа») показує, наскільки двоє розмітників (тут людина і Claude) збігаються в мітках з
                поправкою на випадковість. Просто частка збігів була б завищеною: навіть вгадуючи наосліп, двоє
                іноді ставлять однакову мітку, особливо коли одна мітка трапляється значно частіше за інші.</p>
            <ul>
                <li><b>1</b> — повний збіг; <b>0</b> — збігаються не краще, ніж навмання; менше за 0 — гірше, ніж
                    навмання.</li>
                <li>Орієнтир: до 0.4 — слабка узгодженість, 0.4–0.6 — помірна, 0.6–0.8 — суттєва, понад 0.8 — майже
                    повна.</li>
                <li>У дужках поруч — 95% CI (bootstrap по сніпетах): що вужчий інтервал, то надійніше число.</li>
            </ul>
            <p>Тут κ показує, чи можна довіряти міткам Claude: що вище κ, то менше підстав сумніватися, що людина
                поставила б ті самі мітки.</p>
        </details>

        <details>
            <summary>Що значить колонка «Сніпетів»</summary>
            <ul>
                <li><b>Сніпет</b> — коротка вирізка з відповіді AI навколо згадки бренду: речення зі згадкою плюс по
                    одному сусідньому реченню. Саме сніпет отримує мітку тональності: «рекомендує», «нейтрально» або
                    «негативно».</li>
                <li><b>Відповідь</b> — повна відповідь AI на один запит.</li>
                <li><b>«Сніпетів»</b> — скільки сніпетів з цього бренду розмічено. З кожної відповіді береться один
                    сніпет на бренд, тож це число збігається з кількістю відповідей, у яких бренд згадано.</li>
            </ul>
        </details>

        <div class="legend">
            @foreach ($names as $key => $label)
                <span><i class="dot" style="background: {{ $colors[$key] }}"></i>{{ $label }}</span>
            @endforeach
        </div>

        @foreach ($groups as $subject => $engines)
            @foreach ($engines as $engine => $rows)
                <h2>Запити про {{ $subject }} · {{ $engine }}</h2>
                <div class="scroll">
                <table>
                    <thead>
                    <tr>
                        <th>Згаданий бренд</th><th class="num">Сніпетів</th><th>Розподіл</th>
                        @foreach ($names as $label)<th class="num">{{ $label }}</th>@endforeach
                    </tr>
                    </thead>
                    <tbody>
                    @foreach ($rows as $r)
                        <tr>
                            <td>{{ $r['brand'] }}</td>
                            <td class="num">{{ $r['n_snippets'] }}</td>
                            <td>
                                <div class="bar" role="img" style="display: flex; overflow: hidden"
                                    aria-label="{{ $r['brand'] }}: {{ collect($names)->map(fn ($l, $k) => $l.' '.$pct($r['shares'][$k]['rate']).'%')->implode(', ') }}">
                                    @foreach ($names as $key => $label)
                                        <div style="width: {{ $r['shares'][$key]['rate'] * 100 }}%; background: {{ $colors[$key] }}"></div>
                                    @endforeach
                                </div>
                            </td>
                            @foreach ($names as $key => $label)
                                @php $s = $r['shares'][$key]; @endphp
                                <td class="num">{{ $pct($s['rate']) }}%
                                    @if ($r['ci_available'])
                                        <span class="muted">[{{ $pct($s['ci_low']) }}–{{ $pct($s['ci_high']) }}]</span>
                                    @else
                                        <span class="muted">[CI —]</span>
                                    @endif
                                </td>
                            @endforeach
                        </tr>
                    @endforeach
                    </tbody>
                </table>
                </div>
                @php
                    // Brands with few snippets have huge CIs (2 snippets give [0-100]), so they cannot lead.
                    $minSnippets = 10;
                    $solid = collect($rows)->filter(fn ($r) => $r['n_snippets'] >= $minSnippets && $r['ci_available']);
                    $small = collect($rows)->reject(fn ($r) => $r['n_snippets'] >= $minSnippets && $r['ci_available'])->pluck('brand');
                    // Leader on a share plus whether its CI clears the runner-up's.
                    $leader = function (string $key) use ($solid) {
                        $sorted = $solid->sortByDesc(fn ($r) => $r['shares'][$key]['rate'])->values();
                        $first = $sorted->get(0);
                        $second = $sorted->get(1);
                        if (! $first) return null;
                        $sure = $second && $first['shares'][$key]['ci_low'] > $second['shares'][$key]['ci_high'];
                        return [$first, $second ? $sure : null];
                    };
                    $rec = $leader('recommended');
                    $neg = $leader('negative');
                @endphp
                <p><b>Висновок:</b>
                    @if ($rec)
                        найчастіше з рекомендацією згадують {{ $rec[0]['brand'] }}
                        ({{ $pct($rec[0]['shares']['recommended']['rate']) }}%)
                        @if ($rec[1] === true) — надійно: його CI вище, ніж у наступного бренду.
                        @elseif ($rec[1] === false) — але це недоведено: CI перекриваються з наступним брендом.
                        @else .
                        @endif
                        @if ($neg && $neg[0]['shares']['negative']['rate'] > 0)
                            Найбільша частка негативних — у {{ $neg[0]['brand'] }}
                            ({{ $pct($neg[0]['shares']['negative']['rate']) }}%)
                            @if ($neg[1] === false) — теж недоведено.@elseif ($neg[1] === true) — надійно.@endif
                        @endif
                    @else
                        бракує сніпетів для порівняння.
                    @endif
                    @if ($small->isNotEmpty())
                        У порівняння не входять бренди менш ніж із {{ $minSnippets }} сніпетами
                        ({{ $small->implode(', ') }}): для них даних замало.
                    @endif
                </p>
            @endforeach
        @endforeach
    @endif
@endsection
