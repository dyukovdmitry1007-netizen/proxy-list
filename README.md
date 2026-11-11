# proxy-list

Автоматически обновляемый список бесплатных прокси (http / https / socks4 / socks5).

Скрапер + чекер: [proxy_tool.py](https://github.com/dyukovdmitry1007-netizen/proxy-list) — собирает с 13 публичных источников, проверяет живость и анонимность, сортирует по задержке.

## Файлы

| файл | описание |
|---|---|
| `all.txt` | все уникальные собранные прокси (проверка не пройдена — сырьё) |
| `alive.txt` | живые, ip:port, отсортированы по задержке |
| `alive.json` | живые + страна, протокол, задержка, анонимность |
| `http.txt` / `https.txt` / `socks4.txt` / `socks5.txt` | по протоколам |
| `by-country/` | по странам (DE.txt, RU.txt, ...) |

## Формат

```
protocol://ip:port
```

## Обновление

```bash
python3 proxy_tool.py -c 500 -t 8
cp -r proxies/* .
git add -A && git commit -m "update" && git push
```
