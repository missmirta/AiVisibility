@extends('layouts.app')
@section('title', 'Адаптивний семплінг')
@section('content')
    <h2>Чи дає адаптивний семплінг економію запитів</h2>
    @if (! ($ad['available'] ?? false))
        <div class="note">Немає даних адаптивного семплінгу (потрібні зібрані відповіді в БД).</div>
    @else
        @php
            $policies = ['uniform' => 'рівномірно', 'variance (adaptive)' => 'адаптивно'];
            $colors = ['uniform' => 'var(--muted)', 'variance (adaptive)' => 'var(--accent)'];
            $metrics = [
                'mean' => 'Середня ширина CI по всіх конкурентах',
                'max' => 'Найгірший випадок (найширший CI серед конкурентів)',
            ];
            $target = $ad['target_pp'];
            $conv = $ad['full_convergence'];
            $saving = $conv['adaptive_saving_pct'];
            $draws = fn ($d) => ($d['at_smallest_budget'] ? '≤ ' : ($d['extrapolated'] ? '≈ ' : '')).round($d['draws']);
        @endphp
        <p class="muted">Симуляція на вже зібраних відповідях ({{ $ad['n_arms'] }} пари бренд × движок,
            {{ $ad['n_entities'] }} конкурентів, {{ $ad['n_repeats'] }} повторів). «Рівномірно» — по колу;
            «адаптивно» — наступний запит туди, де CI ще найширший. Ціль — ±{{ $target }} в.п.</p>

        <h2>Однаковий бюджет запитів</h2>
        <p class="muted">Скільки запитів потрібно, щоб ширина CI дійшла до цілі. «≈» — екстраполяція за формою 1/√n,
            а не спостереження; «≤» — ціль досягнута вже на найменшому бюджеті в сітці.</p>
        <div class="scroll">
        <table>
            <thead><tr><th>Метрика</th><th class="num">Рівномірно</th><th class="num">Адаптивно</th><th class="num">Економія (95% CI)</th></tr></thead>
            <tbody>
            @foreach ($metrics as $key => $title)
                @php $m = $ad['fixed_budget'][$key]; $s = $m['savings_pct']; @endphp
                <tr>
                    <td>{{ $title }}</td>
                    <td class="num">{{ $draws($m['draws_to_target']['uniform']) }}</td>
                    <td class="num">{{ $draws($m['draws_to_target']['variance (adaptive)']) }}</td>
                    <td class="num">{{ round($s['value']) }}% [{{ round($s['ci_low']) }}–{{ round($s['ci_high']) }}%]</td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>

        @foreach ($metrics as $key => $title)
            @php
                $curves = $ad['fixed_budget'][$key]['curves'];
                $maxB = max($ad['budgets']);
                $top = max($target, ceil(max(array_map(fn ($c) => max(array_column($c, 'repeat_high')), $curves))));
                $W = 640; $H = 260; $L = 44; $B = 28; $T = 10; $R = 10;
                $x = fn ($b) => $L + ($b / $maxB) * ($W - $L - $R);
                $y = fn ($w) => $T + (1 - min($w, $top) / $top) * ($H - $T - $B);
            @endphp
            <h2>{{ $title }}</h2>
            <svg viewBox="0 0 {{ $W }} {{ $H }}" width="100%" role="img" aria-label="{{ $title }}">
                <line x1="{{ $L }}" y1="{{ $H - $B }}" x2="{{ $W - $R }}" y2="{{ $H - $B }}" stroke="var(--line)"/>
                <line x1="{{ $L }}" y1="{{ $T }}" x2="{{ $L }}" y2="{{ $H - $B }}" stroke="var(--line)"/>
                <line x1="{{ $L }}" y1="{{ $y($target) }}" x2="{{ $W - $R }}" y2="{{ $y($target) }}" stroke="var(--muted)" stroke-dasharray="4 4"/>
                <text x="{{ $L + 4 }}" y="{{ $y($target) - 4 }}">ціль ±{{ $target }} в.п.</text>
                <text x="{{ $L - 6 }}" y="{{ $y(0) + 4 }}" text-anchor="end">0</text>
                <text x="{{ $L - 6 }}" y="{{ $y($top) + 4 }}" text-anchor="end">{{ $top }}</text>
                <text x="{{ $W - $R }}" y="{{ $H - 8 }}" text-anchor="end">бюджет = {{ $maxB }}</text>
                @foreach ($curves as $name => $points)
                    <polyline fill="none" stroke="{{ $colors[$name] ?? 'var(--fg)' }}" stroke-width="2"
                        points="{{ collect($points)->map(fn ($p) => round($x($p['budget']), 1).','.round($y($p['width_pp']), 1))->implode(' ') }}"/>
                @endforeach
            </svg>
            <div class="legend">
                @foreach ($policies as $name => $label)
                    <span><i class="dot" style="background: {{ $colors[$name] }}"></i>{{ $label }}</span>
                @endforeach
            </div>
        @endforeach

        <h2>Коли треба довести кожного конкурента окремо</h2>
        <div class="scroll">
        <table>
            <thead><tr><th>Політика</th><th class="num">Середньо запитів</th><th class="num">σ</th></tr></thead>
            <tbody>
            @foreach ($policies as $name => $label)
                <tr>
                    <td>{{ $label }}</td>
                    <td class="num">{{ round($conv['mean_draws'][$name]) }}</td>
                    <td class="num">{{ round($conv['std_draws'][$name]) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>
        <p>Різниця: {{ round($saving['value'], 1) }}% [{{ round($saving['ci_low'], 1) }}…{{ round($saving['ci_high'], 1) }}%] —
            @if ($saving['distinguishable_from_zero'])
                відрізняється від нуля.
            @else
                <b>у межах шуму</b>: інтервал містить 0. Конкуренти статистично незалежні, тож порядок запитів
                не змінює їхню суму; виграш адаптивності є лише за фіксованого бюджету.
            @endif
        </p>

        <div class="note">CI тут — по повторах симуляції на одному й тому ж скінченному пулі збережених відповідей:
            він не враховує, що сам пул — лише вибірка. Конкуренти з часткою біля 0% отримують майже нульову ширину
            одразу й занижують середнє; тому поряд показано найгірший випадок.</div>
    @endif
@endsection
