@extends('layouts.app')
@section('title', 'Немає даних')
@section('content')
    <div class="note">
        Файл з даними не знайдено: <code>{{ $path }}</code>.<br>
        Запустіть <code>uv run python scripts/export_dashboard_data.py</code> у корені проєкту.
    </div>
@endsection
