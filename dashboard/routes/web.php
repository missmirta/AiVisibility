<?php

use App\Http\Controllers\DashboardController;
use Illuminate\Support\Facades\Route;

Route::get('/', [DashboardController::class, 'methodology'])->name('methodology');
Route::redirect('/methodology', '/');
Route::get('/visibility', [DashboardController::class, 'overview'])->name('overview');
Route::get('/convergence', [DashboardController::class, 'convergence'])->name('convergence');
Route::get('/perception', [DashboardController::class, 'perception'])->name('perception');
Route::get('/representativeness', [DashboardController::class, 'representativeness'])->name('representativeness');
Route::get('/adaptive-sampling', [DashboardController::class, 'adaptiveSampling'])->name('adaptive');
Route::get('/stance', [DashboardController::class, 'stance'])->name('stance');
