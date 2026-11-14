"""Typed billing settings. Defaults live here, never in clients or settlement."""
from backend.core.config import get_config

DEFAULTS = {
    'NEW_USER_FREE_GENERATIONS': '5',
    'TRIAL_ALLOWED_TIERS': 'standard',
    'NEW_USER_POINTS': '10',
    'TIER_COSTS': 'standard:5,hd:10,master:15',
    'INVITE_REWARD_POINTS': '5',
    'INVITE_DAILY_LIMIT': '5',
    'ASSISTANT_MODE_ENABLED': 'true',
}
TIERS = ('standard', 'hd', 'master')


def parse_setting(key, value):
    if key not in DEFAULTS or not isinstance(value, str):
        raise ValueError('不支持的配置项或类型')
    value = value.strip()
    if key == 'ASSISTANT_MODE_ENABLED':
        if value.lower() not in ('true', 'false'):
            raise ValueError('助手开关只能为 true 或 false')
        return value.lower() == 'true'
    if key == 'TRIAL_ALLOWED_TIERS':
        tiers = [v.strip() for v in value.split(',')]
        if not tiers or len(set(tiers)) != len(tiers) or any(v not in TIERS for v in tiers):
            raise ValueError('试用档位必须为 standard、hd、master，以逗号分隔；关闭试用请将次数设为 0')
        return tiers
    if key == 'TIER_COSTS':
        try:
            pairs = [v.strip().split(':') for v in value.split(',')]
            costs = {k.strip(): int(v.strip()) for k, v in pairs}
        except (ValueError, TypeError):
            raise ValueError('价格格式为 standard:5,hd:10,master:15') from None
        if len(pairs) != len(TIERS) or set(costs) != set(TIERS) or any(v < 0 or v > 1000000 for v in costs.values()):
            raise ValueError('价格必须包含三个档位，每项为 0–1000000 的整数')
        return costs
    if not value.isascii() or not value.isdigit() or not 0 <= int(value) <= 1000000:
        raise ValueError('数值必须为 0–1000000 的整数')
    return int(value)


def setting(key):
    return parse_setting(key, str(get_config(key, DEFAULTS[key])))


def new_user_points():
    # Deferred import through get_config avoids ORM initialization cycles.
    return setting('NEW_USER_POINTS')


def registration_grant():
    return {'points': new_user_points(), 'trial_remaining': setting('NEW_USER_FREE_GENERATIONS')}


def public_billing():
    return {'pricing': setting('TIER_COSTS'), 'trial_allowed_tiers': setting('TRIAL_ALLOWED_TIERS'),
            'assistant_mode_enabled': setting('ASSISTANT_MODE_ENABLED'),
            'new_user_points': setting('NEW_USER_POINTS'), 'new_user_free_generations': setting('NEW_USER_FREE_GENERATIONS'),
            'invite_reward_points': setting('INVITE_REWARD_POINTS'), 'invite_daily_limit': setting('INVITE_DAILY_LIMIT')}
