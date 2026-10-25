@extends('layouts.app')
@section('title', 'Видимість брендів')
@section('content')
    <h2>Частка відповідей, де згадано бренд</h2>
    <p class="muted">Смуга — 95% довірчий інтервал (bootstrap), риска — точкова оцінка (одне число з вибірки, наша найкраща здогадка про справжню частку). Якщо інтервали двох
        брендів перекриваються, різниця між ними не доведена. Власний бренд у запитах про себе згадується
        майже завжди, тож він внизу списку й не порівнюється.</p>

    @php
        $axis = 0.1;
        foreach ($groups as $engines) foreach ($engines as $rows) foreach ($rows as $r) $axis = max($axis, $r['ci_high']);
        $axis = min(1.0, ceil($axis * 10) / 10);
    @endphp

    @forelse ($groups as $brand => $engines)
        @foreach ($engines as $engine => $rows)
            <h2>Запити про {{ $brand }} · {{ $engine }} <span class="muted">(n = {{ $rows[0]['n'] }})</span></h2>
            <div class="scroll">
            <table>
                <thead><tr><th>Бренд</th><th>Оцінка</th><th class="num">Частка</th><th class="num">95% CI</th></tr></thead>
                <tbody>
                @foreach ($rows as $r)
                    @php $own = $r['entity'] === $r['subject_brand']; @endphp
                    <tr>
                        <td @class(['own' => $own])>{{ $r['entity'] }}{{ $own ? ' (власний)' : '' }}</td>
                        <td>
                            <div class="bar" role="img" aria-label="{{ $r['entity'] }}: {{ round($r['rate'] * 100) }}%, CI {{ round($r['ci_low'] * 100) }}–{{ round($r['ci_high'] * 100) }}%">
                                <div class="ci" style="left: {{ $r['ci_low'] / $axis * 100 }}%; width: {{ max(0.5, ($r['ci_high'] - $r['ci_low']) / $axis * 100) }}%"></div>
                                <div class="pt" style="left: calc({{ $r['rate'] / $axis * 100 }}% - 1px)"></div>
                            </div>
                        </td>
                        <td class="num">{{ round($r['rate'] * 100) }}%</td>
                        <td class="num">{{ round($r['ci_low'] * 100) }}–{{ round($r['ci_high'] * 100) }}%</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            </div>
        @endforeach
    @empty
        <div class="note">У файлі немає даних про видимість.</div>
    @endforelse
    <p class="muted">Шкала смуг: 0–{{ round($axis * 100) }}%.</p>
@endsection
