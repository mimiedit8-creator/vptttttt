import aiohttp
import logging

LOG = logging.getLogger(__name__)


def _value(item, key, fallback='—'):
    value = item.get(key)
    return str(value) if value not in (None, '') else fallback


def format_parcelle(data: dict, requested_number: str) -> str:
    """Format only fields documented by Parcelle; never infer delivery estimates."""
    state = _value(data, 'RequestState', 'не указан')
    request_error = data.get('RequestErrorText')
    lines = [f'📦 Трек-номер: {requested_number}', f'Состояние запроса: {state}']
    if request_error:
        lines.append(f'Ошибка запроса: {request_error}')
    items = data.get('Items') or []
    if isinstance(items, list) and items:
        for item in items[:3]:
            lines.extend([
                '',
                f"Перевозчик: {_value(item, 'DeliveryCompanyName')}",
                f"Статус: {_value(item, 'CurrentStatus', _value(item, 'DeliveryStatusName'))}",
                f"Местоположение/ПВЗ: {_value(item, 'DeliveryPointAddress')}",
            ])
            if item.get('StorageToDate'):
                lines.append(f"Хранение до: {item['StorageToDate']}")
            if item.get('ErrorText'):
                lines.append(f"Ошибка перевозчика: {item['ErrorText']}")
    elif state in {'New', 'InProgress'}:
        lines.append('Перевозчик ещё обрабатывает запрос. Попробуй проверить позже.')
    elif state == 'Failed':
        lines.append('Parcelle не смог обработать запрос. Проверь номер или попробуй позже.')
    else:
        lines.append('В ответе пока нет сведений о посылке.')
    return '\n'.join(lines)[:3500]


async def track_parcel(number: str, api_key: str, api_url: str):
    if not api_key:
        return 'Для отслеживания нужен PARCELLE_API_KEY. Добавь ключ в .env.'
    url = f'{api_url.rstrip("/")}/tracking/getsync'
    headers = {'Accept': 'application/json', 'X-ApiKey': api_key}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, params={'n': number}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 401 or resp.status == 403:
                    return 'Parcelle отклонил API-ключ. Проверь PARCELLE_API_KEY.'
                if resp.status == 429:
                    return 'Parcelle ограничил частоту запросов. Попробуй позже.'
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        if not isinstance(data, dict):
            return 'Parcelle вернул неожиданный формат ответа.'
        return format_parcelle(data, number)
    except aiohttp.ClientResponseError as exc:
        LOG.warning('Parcelle HTTP error: %s', exc)
        return f'Ошибка Parcelle API: HTTP {exc.status}.'
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        LOG.warning('Parcelle request failed: %s', exc)
        return 'Не удалось связаться с Parcelle. Проверь интернет и попробуй позже.'
