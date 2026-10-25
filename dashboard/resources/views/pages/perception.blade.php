@extends('layouts.app')
@section('title', 'Карта сприйняття')
@section('content')
    <h2>Яким AI бачить бренди за атрибутами</h2>
    @if (! ($perception['available'] ?? false))
        <div class="note">Немає даних попарних порівнянь.</div>
    @else
        @php
            $brands = $perception['brands'];
            $clip = 4.0;
            $attrs = collect($grid)->flatMap(fn ($row) => array_keys($row))->unique()->values();
            $cellStyle = function ($theta) use ($clip) {
                $t = max(-$clip, min($clip, $theta)) / $clip;
                $c = $t >= 0 ? '47,93,138' : '160,65,45';
                return 'background: rgba('.$c.','.round(abs($t) * 0.45, 2).')';
            };
        @endphp
        <p class="muted">Сила бренду θ за моделлю Bradley-Terry із 95% CI (± половина інтервалу). Більше — AI частіше
            обирає бренд. <b>†</b> — один із брендів у цьому атрибуті ніколи не програє (або не виграє), величина θ
            задана регуляризацією, тому показано лише ранг (#1 — найвищий). Це що модель <em>каже</em>, а не факт.</p>

        @foreach ($grid as $engine => $row)
            @php $stats = $perception['engine_stats'][$engine] ?? null; @endphp
            <h2>{{ $engine }}
                @if ($stats)
                    <span class="muted">· відповідей {{ $stats['n'] }}, невалідних {{ round($stats['invalid_share'] * 100, 1) }}%,
                        частка «A» {{ number_format($stats['p_first'], 2) }}
                        [{{ number_format($stats['p_first_ci'][0], 2) }}–{{ number_format($stats['p_first_ci'][1], 2) }}]</span>
                @endif
            </h2>
            <div class="scroll">
            <table>
                <thead>
                <tr>
                    <th>Бренд</th>
                    @foreach ($attrs as $a)
                        <th class="cell">{{ $a }}{{ ($row[$a]['rank_only'] ?? false) ? ' †' : '' }}</th>
                    @endforeach
                </tr>
                </thead>
                <tbody>
                @foreach ($brands as $brand)
                    <tr>
                        <td>{{ $brand }}</td>
                        @foreach ($attrs as $a)
                            @php
                                $cell = $row[$a] ?? null;
                                $b = $cell ? collect($cell['brands'])->firstWhere('brand', $brand) : null;
                            @endphp
                            @if ($b)
                                <td class="cell" @if (! $cell['rank_only']) style="{{ $cellStyle($b['theta']) }}" @endif>
                                    @if ($cell['rank_only'])
                                        #{{ $b['rank'] }}
                                    @else
                                        {{ sprintf('%+.1f', $b['theta']) }}
                                        <small>±{{ number_format(($b['ci_high'] - $b['ci_low']) / 2, 1) }}</small>
                                    @endif
                                </td>
                            @else
                                <td class="cell muted">—</td>
                            @endif
                        @endforeach
                    </tr>
                @endforeach
                </tbody>
            </table>
            </div>

            @php $ties = collect($row)->filter(fn ($c) => count($c['overlapping'])); @endphp
            @if ($ties->count())
                <details>
                    <summary>Пари брендів, які не можна ранжувати (CI перекриваються)</summary>
                    <ul>
                        @foreach ($ties as $a => $c)
                            <li><b>{{ $a }}</b>: {{ collect($c['overlapping'])->map(fn ($p) => $p[0].' ~ '.$p[1])->implode(', ') }}</li>
                        @endforeach
                    </ul>
                </details>
            @endif
        @endforeach

        <h2>Чи однаково движки бачать ринок</h2>
        <p class="muted">Кореляція Спірмена θ по брендах між движками (1 — однаковий порядок).
            Інтранзитивних трійок брендів: {{ $perception['intransitive_triples'] }}.</p>
        <div class="scroll">
        <table>
            <thead><tr><th>Атрибут</th><th class="num">ρ</th></tr></thead>
            <tbody>
            @foreach ($perception['engine_agreement_spearman'] as $a => $rho)
                <tr><td>{{ $a }}</td><td class="num">{{ $rho === null ? 'n/a' : sprintf('%+.2f', $rho) }}</td></tr>
            @endforeach
            </tbody>
        </table>
        </div>
    @endif
@endsection
