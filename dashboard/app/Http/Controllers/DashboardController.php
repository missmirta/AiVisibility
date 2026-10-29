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

    public function model()
    {
        // Screenshots dropped into public/model/ show up on the page; the caption comes from the map below,
        // or from the file name when the file is not listed.
        $captions = [
            'mlflow_training_runs' => 'MLflow: запуски навчання (експеримент stance-classifier, 5 запусків)',
            'mlflow_evaluation_runs' => 'MLflow: запуски оцінки (експеримент stance-classifier-evaluation, 36 запусків)',
            'mlflow_best_finetune_metrics' => 'Найкращий fine-tuned запуск (orderly-hog-300, зерно 2): метрики — gold macro-F1 0.617, κ 0.738',
            'mlflow_best_finetune_gold_report' => 'Той самий запуск, gold_report.json: precision / recall / F1 по класах на 120 людських мітках',
            'mlflow_model_registry' => 'MLflow: реєстр моделей (stance-classifier, остання версія 4, production → версія 2)',
        ];
        $shots = collect(glob(public_path('model/*.{png,jpg,jpeg,gif,webp}'), GLOB_BRACE) ?: [])
            ->sort()
            ->map(fn ($path) => [
                'url' => asset('model/'.basename($path)),
                'caption' => $captions[pathinfo($path, PATHINFO_FILENAME)]
                    ?? str_replace(['_', '-'], ' ', pathinfo($path, PATHINFO_FILENAME)),
            ])
            ->values()
            ->all();

        return $this->page('pages.model', fn () => ['shots' => $shots]);
    }

    public function conclusions()
    {
        return $this->page('pages.conclusions');
    }

    public function methodology()
    {
        return $this->page('pages.methodology');
    }
}
