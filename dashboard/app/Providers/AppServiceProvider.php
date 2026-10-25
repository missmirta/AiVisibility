<?php

namespace App\Providers;

use App\Services\DashboardData;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(DashboardData::class, fn () => new DashboardData(config('dashboard.data_path')));
    }

    public function boot(): void
    {
        //
    }
}
