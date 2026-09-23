# Submission checklist

- [ ] Открыт PR в `Dev-No1se`; merge и отправка заявки выполняются владельцем.
- [ ] В PR приложены `FINAL_RELEASE_ACCEPTANCE.md`, large-repo URL/HEAD и безопасные test logs.
- [ ] Для demo выбраны 5–8 screenshots; fixture и live screenshots подписаны раздельно.
- [ ] В видео не попали PAT, OAuth secrets, `.env`, cookies, private repositories и персональные данные.
- [ ] AppSec помечен PASS только при подтверждённом поддерживаемом API; иначе оставлен `NO_DATA` с evidence.
- [ ] Реальный Yandex browser flow пройден владельцем вручную либо явно оставлен BLOCKED.
- [ ] Deployment выполнен владельцем после проверки `.env.production.example` и HTTPS callback.
