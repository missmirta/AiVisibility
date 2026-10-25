<?php

return [
    // JSON produced by scripts/export_dashboard_data.py (the dashboard only displays it).
    'data_path' => env('DASHBOARD_DATA') ?: base_path('../data/reports/dashboard.json'),
];
