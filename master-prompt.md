# 🎯 РОЛЬ И КОНТЕКСТ
Ты — Senior AI Engineer & DevOps-архитектор. Твоя задача — сгенерировать полностью готовый к запуску проект для реализации **Role-Chaining Pipeline** (одна LLM, последовательная смена ролей по шагам 1→9). Проект должен строго соответствовать агентной логике, структуре артефактов и принципам fail-fast/feedback loops.

# 📋 ЗАДАЧА
Создай полную файловую структуру проекта с рабочим кодом, конфигурациями, JSON-схемами валидации и промпт-шаблонами. Всё должно быть готово к запуску командой `python scripts/run_pipeline.py --goal "..."`.

# ⚙️ ЖЁСТКИЕ ТРЕБОВАНИЯ
1. Язык: Python 3.10+
2. Зависимости: `pyyaml`, `jsonschema`, `python-dotenv`, `requests` (или `openai`), `jinja2` (или ручная подстановка `{{}}`)
3. Не используй заглушки (`...`, `# TODO`, `pass`) в критических файлах. Пиши полностью рабочий код.
4. Все промпты должны использовать маркеры `[ШАГ X: РОЛЬ]`, требовать строгого JSON-вывода в ````json ... ```` и содержать обработку ошибок/возвратов.
5. Состояние хранится ВНЕ контекста модели через `ArtifactStore`. В контекст передаются только ссылки или дайджесты.
6. Валидация артефактов по JSON Schema перед переходом на следующий шаг.
7. Поддержка feedback loops: Тестировщик → Билдер (max 2 повтора), Критик → Билдер/Промпт-инженер.
8. Логирование каждого шага в `pipeline.log` + сохранение метаданных в `meta.json`.

# 🗂 ТРЕБУЕМАЯ СТРУКТУРА И СОДЕРЖИМОЕ
Сгенерируй ВСЕ файлы в указанной структуре. Для каждого файла укажи полный путь и содержимое.

📁 `.gitignore` → Исключить: `.env`, `artifacts/run_*/`, `__pycache__`, `*.log`, `venv/`
📁 `.env.example` → `LLM_API_KEY=`, `LLM_BASE_URL=`, `LLM_MODEL=`
📁 `requirements.txt` → Список зависимостей
📁 `README.md` → Краткое описание, как запустить, структура, логика пайплайна

📁 `config/pipeline.yaml` → Описание шагов 1-9, таймауты, `input_from`, `on_failure` с `retry_step` и `max_retries`
📁 `config/models.yaml` → Карта ролей → моделей (заглушка для single-LLM, но с возможностью расширения)
📁 `config/schemas/` → JSON Schema для: `plan.schema.json`, `ard.schema.json`, `tdd.schema.json`, `prompt_package.schema.json`, `test_report.schema.json`, `quality_review.schema.json`, `security_audit.schema.json`

📁 `prompts/_base.md` → Глобальные правила, формат вывода, запрет на галлюцинации
📁 `prompts/snippets/` → `role_switch_marker.md`, `json_output_rule.md`, `error_handling.md`, `feedback_loop_rule.md`
📁 `prompts/01_orchestrator.md` → `prompts/09_security.md` → Полные промпты для каждого шага с подстановками `{{artifact_X}}`, чёткими инструкциями и строгой JSON-схемой вывода

📁 `src/__init__.py` → Пустой
📁 `src/llm_client.py` → Класс для вызова LLM (поддержка OpenAI-compatible API, retry, timeout, парсинг ответа)
📁 `src/artifact_store.py` → Сохранение/загрузка артефактов, логирование, генерация `run_id`, метод `get_summary()`
📁 `src/validators.py` → Валидация по JSON Schema, авто-запрос исправления при mismatch
📁 `src/utils.py` → Парсинг JSON из markdown, форматирование дайджестов, хелперы
📁 `src/pipeline_runner.py` → Основной движок: чтение YAML, цикл по шагам, подстановка артефактов, обработка `on_failure`, сохранение `meta.json`

📁 `scripts/run_pipeline.py` → CLI точка входа (`--goal`, `--config`, `--resume`)
📁 `scripts/replay_run.py` → Перезапуск конкретного шага из сохранённого `run_id`

# 📤 ФОРМАТ ВЫВОДА
Выдавай ответ СТРОГО в следующем формате для каждого файла:
📁 Путь: `path/to/file.ext`
```{язык}
[полное содержимое файла]
```

Не комментируй процесс. Не сокращай код. Не пропускай файлы. Начинай генерацию сразу с `.gitignore`.
