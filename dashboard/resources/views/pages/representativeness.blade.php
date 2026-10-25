@extends('layouts.app')
@section('title', 'Репрезентативність')
@section('content')
    <h2>Чи схожі наші запити на реальні</h2>
    @if (! ($rep['available'] ?? false))
        <div class="note">Немає даних репрезентативності (потрібні запити в БД і <code>real_queries.json</code>).</div>
    @else
        @php
            $labels = [
                'all_real' => 'усі реальні',
                'choice_only' => 'лише питання про вибір/порівняння',
                'length_matched' => 'реальні, підібрані за довжиною',
                'length_only' => 'лише довжина (контроль стилю)',
            ];
            $verdicts = [
                'no_change' => 'без змін',
                'stable_sign' => 'стабільний знак',
                'mixed_sign' => 'знак мінливий',
            ];
            $pct = fn ($x) => round($x * 100);
        @endphp
        <p class="muted">Класифікатор вчиться відрізняти {{ $rep['n_synthetic'] }} синтетичних запитів від
            {{ $rep['n_real'] }} реальних. AUC 0.5 — не відрізнити, 1.0 — повністю різні. p — з permutation-тесту
            ({{ $rep['permutations'] }} перестановок), тому не буває меншим за 1/{{ $rep['permutations'] + 1 }}.</p>
        <div class="scroll">
        <table>
            <thead><tr><th>Вибірка</th><th class="num">n синт. / n реальних</th><th class="num">AUC</th>
                <th class="num">AUC випадково</th><th class="num">p</th></tr></thead>
            <tbody>
            @foreach ($rep['two_sample'] as $key => $r)
                <tr>
                    <td>{{ $labels[$key] ?? $key }}</td>
                    <td class="num">{{ $r['n_synthetic'] }} / {{ $r['n_real'] }}</td>
                    <td class="num">{{ number_format($r['auc'], 3) }}</td>
                    <td class="num">≈{{ number_format($r['null_mean_auc'], 3) }}</td>
                    <td class="num">{{ number_format($r['p_value'], 4) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>

        @php $cl = $rep['clusters']; @endphp
        <h2>Теми запитів і ваги</h2>
        <p class="muted">Обидва набори кластеризовано разом: k = {{ $cl['k'] }}, silhouette
            {{ number_format($cl['silhouette'], 2) }} (низька, тож межі тем умовні). Вага кластера —
            частка реальних / частка синтетичних, обмежена зверху.
            @if ($cl['uncovered_real_share'] > 0)
                {{ $pct($cl['uncovered_real_share']) }}% реальних питань у темах без жодного синтетичного запиту:
                для них перезважити неможливо.
            @endif
        </p>
        <div class="scroll">
        <table>
            <thead><tr><th>#</th><th class="num">Синтетичні</th><th class="num">Реальні</th><th class="num">Вага</th>
                <th>Приклади</th></tr></thead>
            <tbody>
            @foreach ($cl['items'] as $c)
                <tr>
                    <td>{{ $c['id'] }}</td>
                    <td class="num">{{ round($c['p_synthetic'] * 100, 1) }}%</td>
                    <td class="num">{{ round($c['p_real'] * 100, 1) }}%</td>
                    <td class="num">{{ number_format($c['weight'], 2) }}</td>
                    <td>{{ collect($c['examples'])->map(fn ($e) => '«'.\Illuminate\Support\Str::limit($e, 70).'»')->implode(' · ') }}
                        @if ($c['uncovered']) <b>† немає в нашому наборі</b> @endif</td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>

        <h2>Як перезважування рухає частку згадок</h2>
        <p class="muted">Частка згадок конкурента без ваг і з вагами, 95% CI (зважений bootstrap). CI враховує лише
            шум відповідей, а не вибір кластеризації: тому показано розкид зважених оцінок для 7 конфігурацій k/seed.
            n_eff — скільки незважених відповідей варта зважена вибірка. Перекриті інтервали — не доведена зміна.</p>
        <div class="scroll">
        <table>
            <thead><tr><th>Бренд / движок / сутність</th><th class="num">Без ваг</th><th class="num">З вагами</th>
                <th class="num">Δ в.п.</th><th class="num">n_eff</th><th class="num">Розкид з вагами</th><th>Знак</th></tr></thead>
            <tbody>
            @foreach ($rep['mentions'] as $m)
                @php $u = $m['unweighted']; $w = $m['weighted']; $s = $m['sensitivity']; $delta = round(($w['rate'] - $u['rate']) * 100, 1) + 0; @endphp
                <tr>
                    <td>{{ $m['subject_brand'] }} / {{ $m['engine'] }} / {{ $m['entity'] }}</td>
                    <td class="num">{{ $pct($u['rate']) }}% <small>[{{ $pct($u['ci_low']) }}–{{ $pct($u['ci_high']) }}]</small></td>
                    <td class="num">{{ $pct($w['rate']) }}% <small>[{{ $pct($w['ci_low']) }}–{{ $pct($w['ci_high']) }}]</small></td>
                    <td class="num">{{ sprintf('%+.1f', $delta) }}</td>
                    <td class="num">{{ round($m['n_eff']) }}</td>
                    <td class="num">{{ $pct($s['min']) }}–{{ $pct($s['max']) }}%</td>
                    <td>{{ $verdicts[$s['verdict']] ?? $s['verdict'] }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
        </div>
        <div class="note">Чесне формулювання: оцінку конкурентів Stripe, найімовірніше, занижено, але на скільки — з цими
            даними сказати не можна. Для Paddle ваги нічого не змінюють: усі його запити потрапляють в один кластер.
            Тобто це не доказ, що запити Paddle репрезентативні.</div>
    @endif
@endsection
