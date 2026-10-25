<?php

namespace Tests\Feature;

use App\Services\DashboardData;
use Tests\TestCase;

class DashboardPagesTest extends TestCase
{
    private function useData(string $path): void
    {
        $this->app->singleton(DashboardData::class, fn () => new DashboardData($path));
    }

    private function useFixture(): void
    {
        $this->useData(base_path('tests/fixtures/dashboard.json'));
    }

    public function test_overview_shows_rate_with_ci(): void
    {
        $this->useFixture();

        $this->get('/visibility')->assertOk()->assertSee('Adyen')->assertSee('Видимість брендів');
    }

    public function test_convergence_renders_curve(): void
    {
        $this->useFixture();

        $this->get('/convergence')->assertOk()->assertSee('<polyline', false);
    }

    public function test_perception_marks_rank_only_and_overlaps(): void
    {
        $this->useFixture();

        $this->get('/perception')->assertOk()
            ->assertSee('fast_payouts †')
            ->assertSee('#1')
            ->assertSee('Stripe ~ Paddle');
    }

    public function test_representativeness_shows_two_sample_clusters_and_weighted_ci(): void
    {
        $this->useFixture();

        $this->get('/representativeness')->assertOk()
            ->assertSee('0.950')
            ->assertSee('† немає в нашому наборі')
            ->assertSee('Stripe / claude / Adyen')
            ->assertSee('[15–45]')
            ->assertSee('стабільний знак');
    }

    public function test_representativeness_without_section_shows_notice(): void
    {
        $path = sys_get_temp_dir().'/dashboard_no_rep.json';
        $data = json_decode(file_get_contents(base_path('tests/fixtures/dashboard.json')), true);
        unset($data['representativeness']);
        file_put_contents($path, json_encode($data));
        $this->useData($path);

        $this->get('/representativeness')->assertOk()->assertSee('Немає даних репрезентативності');
        unlink($path);
    }

    public function test_adaptive_sampling_shows_savings_with_ci_and_noise_verdict(): void
    {
        $this->useFixture();

        $this->get('/adaptive-sampling')->assertOk()
            ->assertSee('76% [61–84%]')
            ->assertSee('≈ 532')
            ->assertSee('<polyline', false)
            ->assertSee('у межах шуму');
    }

    public function test_stance_shows_shares_with_ci_and_teacher_agreement(): void
    {
        $this->useFixture();

        $this->get('/stance')->assertOk()
            ->assertSee('Adyen')
            ->assertSee('[20–30]')
            ->assertSee('[CI —]')
            ->assertSee('0.74')->assertSee('[0.62–0.84]');
    }

    public function test_new_sections_without_data_show_notice(): void
    {
        $path = sys_get_temp_dir().'/dashboard_no_new.json';
        $data = json_decode(file_get_contents(base_path('tests/fixtures/dashboard.json')), true);
        unset($data['adaptive_sampling'], $data['stance']);
        file_put_contents($path, json_encode($data));
        $this->useData($path);

        $this->get('/adaptive-sampling')->assertOk()->assertSee('Немає даних адаптивного семплінгу');
        $this->get('/stance')->assertOk()->assertSee('Немає даних про тональність');
        unlink($path);
    }

    public function test_methodology_renders(): void
    {
        $this->useFixture();

        $this->get('/')->assertOk()->assertSee('Що вимірюємо');
        $this->get('/methodology')->assertRedirect('/');
    }

    public function test_footer_shows_run_metadata(): void
    {
        $this->useFixture();

        $this->get('/')->assertSee('abc1234');
    }

    public function test_missing_data_file_gives_503_with_hint(): void
    {
        $this->useData(base_path('tests/fixtures/nope.json'));

        $this->get('/')->assertStatus(503)->assertSee('export_dashboard_data.py');
    }
}
