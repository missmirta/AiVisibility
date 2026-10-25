<?php

namespace App\Services;

use RuntimeException;

/**
 * Reads the exported JSON. No statistics are computed here: every number,
 * including its confidence interval, comes from the Python side.
 */
class DashboardData
{
    private ?array $data = null;

    public function __construct(private readonly string $path)
    {
    }

    public function exists(): bool
    {
        return is_file($this->path);
    }

    public function all(): array
    {
        if ($this->data === null) {
            if (! $this->exists()) {
                throw new RuntimeException("Немає файлу {$this->path}. Запустіть scripts/export_dashboard_data.py.");
            }
            $decoded = json_decode(file_get_contents($this->path), true, 512, JSON_THROW_ON_ERROR);
            $this->data = $decoded;
        }

        return $this->data;
    }

    public function meta(): array
    {
        return $this->all()['meta'] ?? [];
    }

    /** Mention rates grouped as [subject_brand][engine] => rows, own brand last. */
    public function visibility(): array
    {
        $groups = [];
        foreach ($this->all()['visibility'] ?? [] as $row) {
            $groups[$row['subject_brand']][$row['engine']][] = $row;
        }
        foreach ($groups as &$engines) {
            foreach ($engines as &$rows) {
                usort($rows, fn ($a, $b) => [$a['entity'] === $a['subject_brand'], -$a['rate']]
                    <=> [$b['entity'] === $b['subject_brand'], -$b['rate']]);
            }
        }

        return $groups;
    }

    public function convergence(): array
    {
        return $this->all()['convergence'] ?? [];
    }

    public function perception(): array
    {
        return $this->all()['perception'] ?? ['available' => false];
    }

    public function representativeness(): array
    {
        return $this->all()['representativeness'] ?? ['available' => false];
    }

    public function adaptiveSampling(): array
    {
        return $this->all()['adaptive_sampling'] ?? ['available' => false];
    }

    public function stance(): array
    {
        return $this->all()['stance'] ?? ['available' => false];
    }

    /** Stance rows grouped as [subject_brand][engine] => rows, most snippets first. */
    public function stanceGroups(): array
    {
        $groups = [];
        foreach ($this->stance()['items'] ?? [] as $row) {
            $groups[$row['subject_brand']][$row['engine']][] = $row;
        }
        foreach ($groups as &$engines) {
            foreach ($engines as &$rows) {
                usort($rows, fn ($a, $b) => $b['n_snippets'] <=> $a['n_snippets']);
            }
        }

        return $groups;
    }

    /** Perception cells indexed as [engine][attribute]. */
    public function perceptionGrid(): array
    {
        $grid = [];
        foreach ($this->perception()['cells'] ?? [] as $cell) {
            $grid[$cell['engine']][$cell['attribute']] = $cell;
        }

        return $grid;
    }
}
