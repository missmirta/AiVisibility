FROM php:8.4-cli

RUN apt-get update && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-interaction --prefer-dist
COPY . .
# .env.example already uses array session/cache and sync queue: no database needed.
RUN cp .env.example .env
RUN composer dump-autoload --no-dev --optimize && php artisan package:discover --ansi

EXPOSE 8000
# `artisan serve` drops env vars (APP_KEY, DASHBOARD_DATA), so run the built-in server directly, as it does.
# Throwaway key per start: no auth, sessions in memory.
CMD ["sh", "-c", "export APP_KEY=$(php artisan key:generate --show) && cd public && exec php -S 0.0.0.0:8000 ../vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php"]
