@extends('layouts.app')
@section('title', 'Збіжність')
@section('content')
    <h2>Скільки запитів потрібно для потрібної точності</h2>
    <p class="muted">Середня половина ширини 95% CI для частки згадок конкурента залежно від кількості
        відповідей n (підвибірки з уже зібраних даних). Пунктир — ціль ±5 в.п.</p>

    @php
        $colors = ['claude' => 'var(--accent)', 'openai' => 'var(--neg)'];
        $maxN = 1; $maxW = 5;
        foreach ($engines as $e) {
            foreach ($e['curve'] as $p) {
                $maxN = max($maxN, $p['n']);
                $maxW = max($maxW, $p['half_width_pp']);
            }
        }
        $top = ceil($maxW);
        $W = 640; $H = 300; $L = 44; $B = 28; $T = 10; $R = 10;
        $x = fn ($n) => $L + ($n / $maxN) * ($W - $L - $R);
        $y = fn ($w) => $T + (1 - $w / $top) * ($H - $T - $B);
    @endphp

    @if (count($engines))
        <svg viewBox="0 0 {{ $W }} {{ $H }}" width="100%" role="img" aria-label="Криві збіжності">
            <line x1="{{ $L }}" y1="{{ $H - $B }}" x2="{{ $W - $R }}" y2="{{ $H - $B }}" stroke="var(--line)"/>
            <line x1="{{ $L }}" y1="{{ $T }}" x2="{{ $L }}" y2="{{ $H - $B }}" stroke="var(--line)"/>
            <line x1="{{ $L }}" y1="{{ $y(5) }}" x2="{{ $W - $R }}" y2="{{ $y(5) }}" stroke="var(--muted)" stroke-dasharray="4 4"/>
            <text x="{{ $L + 4 }}" y="{{ $y(5) - 4 }}">ціль ±5 в.п.</text>
            <text x="{{ $L - 6 }}" y="{{ $y(0) + 4 }}" text-anchor="end">0</text>
            <text x="{{ $L - 6 }}" y="{{ $y($top) + 4 }}" text-anchor="end">{{ $top }}</text>
            <text x="{{ $W - $R }}" y="{{ $H - 8 }}" text-anchor="end">n = {{ $maxN }}</text>
            <text x="{{ $L }}" y="{{ $H - 8 }}">n</text>
            @foreach ($engines as $engine => $e)
                <polyline fill="none" stroke="{{ $colors[$engine] ?? 'var(--fg)' }}" stroke-width="2"
                    points="{{ collect($e['curve'])->map(fn ($p) => round($x($p['n']), 1).','.round($y($p['half_width_pp']), 1))->implode(' ') }}"/>
            @endforeach
        </svg>
        <div class="legend">
            @foreach ($engines as $engine => $e)
                <span><i class="dot" style="background: {{ $colors[$engine] ?? 'var(--fg)' }}"></i>{{ $engine }}</span>
            @endforeach
        </div>

        <div class="scroll">
        <table>
            <thead><tr><th>Движок</th><th class="num">Спостережено до n</th><th class="num">Ширина на макс. n</th><th>Ціль ±5 в.п.</th></tr></thead>
            <tbody>
            @foreach ($engines as $engine => $e)
                @php $last = end($e['curve']); @endphp
                <tr>
                    <td>{{ $engine }}</td>
                    <td class="num">{{ $last['n'] }}</td>
                    <td class="num">±{{ number_format($last['half_width_pp'], 1) }} в.п.</td>
                    <td>
                        @if ($e['observed_n'])
                            досягнуто на n = {{ $e['observed_n'] }}<br>
                            <span class="muted">за формою кривої 1/√n: ≈ {{ $e['curve_fit_n'] }} запитів</span>
                        @else
                            не досягнуто; екстраполяція ≈ {{ $e['extrapolated_n'] }} запитів
                        @endif
                    </td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>
        <div class="note">Екстраполяція — це продовження форми кривої 1/√n, підігнане на малих n, а не спостереження
            і не універсальна формула розміру вибірки. Класична біноміальна оцінка дає приблизно вдвічі більше;
            для планування розумніше брати вище значення.</div>
    @else
        <div class="note">У файлі немає кривих збіжності.</div>
    @endif
@endsection
