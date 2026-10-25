<?php

namespace App\Http\Controllers;

use App\Services\DashboardData;

class DashboardController extends Controller
{
    public function __construct(private readonly DashboardData $data)
    {
    }

    private function page(string $view, ?callable $extra = null)
    {
        if (! $this->data->exists()) {
            return response()->view('pages.missing', ['path' => config('dashboard.data_path')], 503);
        }

        return view($view, ['meta' => $this->data->meta()] + ($extra ? $extra() : []));
    }

    public function overview()
    {
        return $this->page('pages.overview', fn () => ['groups' => $this->data->visibility()]);
    }

    public function convergence()
    {
        return $this->page('pages.convergence', fn () => ['engines' => $this->data->convergence()]);
    }

    public function perception()
    {
        return $this->page('pages.perception', fn () => [
            'perception' => $this->data->perception(),
            'grid' => $this->data->perceptionGrid(),
        ]);
    }

    public function representativeness()
    {
        return $this->page('pages.representativeness', fn () => ['rep' => $this->data->representativeness()]);
    }

    public function adaptiveSampling()
    {
        return $this->page('pages.adaptive_sampling', fn () => ['ad' => $this->data->adaptiveSampling()]);
    }

    public function stance()
    {
        return $this->page('pages.stance', fn () => [
            'stance' => $this->data->stance(),
            'groups' => $this->data->stanceGroups(),
        ]);
    }

    public function methodology()
    {
        return $this->page('pages.methodology');
    }
}
