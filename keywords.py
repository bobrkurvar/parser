

CONTENT_KEYWORDS = {
    # python stack
    "python",
    "питон",
    "django",
    "fastapi",
    "flask",
    "aiohttp",

    # backend
    "backend",
    "бекенд",
    "бэкенд",
    "сервер",
    "серверная часть",
    "api",
    "апи",
    "rest",
    "json",
    "webhook",
    "вебхук",
    "интеграция",
    "интегрировать",

    # bots / messengers
    "бот",
    "чат-бот",
    "telegram",
    "телеграм",
    "tg",
    "mini app",
    "telegram mini app",
    "уведомления",

    # parsing / automation / scripts
    "парсинг",
    "парсер",
    "scraping",
    "скрапинг",
    "сбор данных",
    "выгрузка данных",
    "скрипт",
    "скрипты",
    "автоматизация",
    "автоматизировать",
    "обработка данных",
    "обработка файлов",

    # databases
    "база данных",
    "бд",
    "postgresql",
    "postgres",
    "sqlite",
    "mysql",
    "redis",
    "sql",

    # sites / web apps
    "личный кабинет",
    "админка",
    "панель управления",
    "dashboard",
    "форма заявки",
    "заявка",
    "заявки",
    "сайт",
    "mvp",
    "прототип",
    "веб-приложение",
    "web app",

    # crm / erp
    "crm",
    "erp",
    "amocrm",
    "amo crm",
    "amoCRM",
    "воронка",
    "сделки",
    "лиды",
    "клиенты",
    "менеджеры",
    "заявки",
    "битрикс24",
    "bitrix24",
}

EXCLUDED_STACK_PATTERNS = {
    "go": [
        r"\bgolang\b",
        r"\bgo\b",
        r"\bна go\b",
        r"\bна golang\b",
    ],

    "php": [
        r"\bphp\b",
        r"\blaravel\b",
        r"\bsymfony\b",
        r"\byii\b",
        r"\byii2\b",
    ],

    "cms_php": [
        r"\bwordpress\b",
        r"\bwp\b",
        r"\bwoocommerce\b",
        r"\bopencart\b",
        r"\bjoomla\b",
        r"\bdrupal\b",
        r"\bmodx\b",
        r"\bmagento\b",
        r"\bprestashop\b",
        r"\bcs-cart\b",
        r"\bbitrix\b",
        r"\bбитрикс\b",
        r"\b1c-bitrix\b",
        r"\b1с-битрикс\b",
    ],

    "java": [
        r"\bjava\b",
        r"\bspring\b",
    ],

    "csharp": [
        r"\bc#\b",
        r"\b\.net\b",
        r"\bdotnet\b",
        r"\basp\.net\b",
    ],

    "mobile_native": [
        r"\bswift\b",
        r"\bkotlin\b",
        r"\bflutter\b",
        r"\bdart\b",
    ],

    "one_c": [
        r"\b1c\b",
        r"\b1с\b",
        r"\b1c бухгалтерия\b",
        r"\b1с бухгалтерия\b",
        r"\bконфигурац\w* 1с\b",
    ],

    "node": [
        r"\bnode\.js\b",
        r"\bnodejs\b",
        r"\bnest\.js\b",
        r"\bnestjs\b",
    ],

    "frontend_only": [
        r"\bhtml/css\b",
        r"\bhtml css\b",
        r"\bверстк\w*\b",
        r"\breact\b",
        r"\bvue\b",
        r"\bangular\b",
    ],

    "no_code_site_builders": [
        r"\btilda\b",
        r"\bтильд\w*\b",
        r"\bwebflow\b",
        r"\bwix\b",
    ],

    "design_only": [
        r"\bfigma\b",
        r"\bui/ux\b",
        r"\bux/ui\b",
        r"\bмакет\w*\b",
        r"\bдизайн\b",
        r"\bредизайн\b",
    ],
}
