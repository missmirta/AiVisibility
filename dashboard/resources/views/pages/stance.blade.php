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
                        <th>Згаданий бренд</th><th class="num">Сніпетів / відповідей</th><th>Розподіл</th>
                        @foreach ($names as $label)<th class="num">{{ $label }}</th>@endforeach
                    </tr>
                    </thead>
                    <tbody>
                    @foreach ($rows as $r)
                        <tr>
                            <td>{{ $r['brand'] }}</td>
                            <td class="num">{{ $r['n_snippets'] }} / {{ $r['n_responses'] }}</td>
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
            @endforeach
        @endforeach
    @endif
@endsection
