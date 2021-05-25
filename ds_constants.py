import habitat
import tools

class DS_Constants: 
    REV_CHANNEL_SENTINEL = 'none' 
    REV_CHANNEL_KEY = 'rev_channel' 
    REV_INTERVAL_KEY = 'rev_interval' 
    REV_LAST_CHECKED_KEY = 'rev_last_checked' 

    DEFAULT_PREFIX = ',' 
    MAX_PREFIX = 5
    PREFIX_SENTINEL = 'none' 

    LINK_SENTINEL = 'remove' 
    LINK_HELP_IMG = 'https://cdn.discordapp.com/attachments/493952969277046787/796576600413175819/linking_instructions.png' 
    INVITE_LINK = 'https://discord.com/oauth2/authorize?client_id=796151711571116042&permissions=347136&scope=bot' 

    DATE_FORMAT = '%B %d, %Y' 
    REV_LOG_TIME_FORMAT = '%m-%d-%Y at %I:%M:%S %p' 
    MESSAGE_LOG_TIME_FORMAT = REV_LOG_TIME_FORMAT

    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    TRAIL_OFF = '...' 
    MAX_LOG = 1000000
    MAX_SEARCH_TIME = 60
    MAX_SKIN_SUGGESTIONS = 10

    OWNER_ID = 315682382147485697

    MENTION_REGEX = '\A<@!?(?P<member_id>[0-9]+)>\Z' 
    CHANNEL_REGEX = '\A<#(?P<channel_id>[0-9]+)>\Z' 

    DATA_URL_TEMPLATE = 'https://api.deeeep.io/users/{}' 
    PFP_URL_TEMPLATE = 'https://deeeep.io/files/{}' 
    SERVER_LIST_URL = 'http://api.deeeep.io/hosts?beta=1' 
    MAP_URL_TEMPLATE = 'https://api.deeeep.io/maps/{}' 
    SKINS_LIST_URL = 'https://api.deeeep.io/skins?cat=all' 
    LOGIN_URL = 'https://api.deeeep.io/auth/local/signin' 
    SKIN_BOARD_MEMBERS_URL = 'https://api.deeeep.io/users/boardMembers' 
    LOGOUT_URL = 'https://api.deeeep.io/auth/logout' 
    PFP_REGEX = '\A(?:https?://)?(?:www\.)?deeeep\.io/files/(?P<acc_id>[0-9]+)(?:-temp)?\.[0-9A-Za-z]+(?:\?.*)?\Z' 

    DEFAULT_PFP = 'https://deeeep.io/new/assets/placeholder.png' 

    SKIN_ASSET_URL_TEMPLATE = 'https://deeeep.io/assets/skins/{}' 
    CUSTOM_SKIN_ASSET_URL_ADDITION = 'custom/' 
    SKIN_URL_TEMPLATE = 'https://api.deeeep.io/skins/{}' 
    SKIN_REVIEW_TEMPLATE = 'https://api.deeeep.io/skins/{}/review' 

    STONKS_THRESHOLD = 150

    STAT_CHANGE_TRANSLATIONS = {
        'HM': 'healthMultiplier', 
        'DM': 'damageMultiplier', 
        'DB': 'damageBlock', 
        'DR': 'damageReflection', 
        'AP': 'armorPenetration', 
        'BR': 'bleedReduction', 
        'OT': 'oxygenTime', 
        'TT': 'temperatureTime', 
        'PT': 'pressureTime', 
        'ST': 'salinityTime', 
        'SS': 'sizeMultiplier', 
        'HA': 'habitat', 
    } 

    STAT_FORMATS = {
        'boosts': ('boosts', '{}'), 
        'level': ('tier', '{}', lambda num: num + 1), 
        'oxygenTime': ('oxygen time', '{}s'), 
        'temperatureTime': ('temperature time', '{}s'),
        'pressureTime': ('pressure time', '{}s'),
        'salinityTime': ('salinity time', '{}s'),
        'speedMultiplier': ('base speed', '{:.0%}'),
        'walkSpeedMultiplier': ('walk speed', '{:.0%}'),
        'sizeMultiplier': ('size scale', '{}x', lambda num: float(num)), 
        'sizeScale': ('dimensions', "{0['x']} x {0['y']}"),
        'damageMultiplier': ('damage', '{}', lambda num: tools.trunc_float(num * 20)), 
        'healthMultiplier': ('health', '{} HP', lambda num: tools.trunc_float(num * 100)),
        'damageBlock': ('armor', '{}%', 100),
        'damageReflection': ('damage reflection', '{}%', 100), 
        'bleedReduction': ('bleed reduction', '{}%', 100), 
        'armorPenetration': ('armor penetration', '{}%', 100), 
        'habitat': ('habitat', '{}', lambda num: habitat.Habitat(num)), 
        'secondaryAbilityLoadTime': ('charged boost load time', '{} ms'), 
    }
    
    NORMAL_STATS = 'level', 'healthMultiplier', 'damageMultiplier', 'speedMultiplier', 'sizeMultiplier', 'damageBlock', 'damageReflection', 'bleedReduction', \
'armorPenetration' 
    BIOME_STATS = 'oxygenTime', 'temperatureTime', 'pressureTime', 'salinityTime' 

    BOOLEANS = 'canFly', 'canSwim', 'needsAir', 'canClimb', 'poisonResistant', 'ungrabbable', 'canDig', 'canWalkUnderwater' 
    
    OLD_STAT_MULTIPLIERS = {
        'DB': 100, 
        'DR': 100, 
        'AP': 100, 
        'BR': 100, 
    }
    STAT_CHANGE_CONVERTERS = {
        'HM': lambda num: tools.trunc_float(num * 100), 
        'DM': lambda num: tools.trunc_float(num * 20), 
        'SS': lambda num: float(num), 
        'HA': lambda num: habitat.Habitat(num), 
    }

    SKIN_REVIEW_LIST_URL = 'https://api.deeeep.io/skins/pending?t=review' 
    STATS_UNBALANCE_BLACKLIST = ['OT', 'TT', 'PT', 'ST', 'SS', 'HA'] 
    FLOAT_CHECK_REGEX = '\A(?P<abs_val>[-+][0-9]+(?:\.[0-9]+)?)\Z' 
    REDDIT_LINK_REGEX = '\A(?:https?://)?(?:www\.)?reddit\.com/(?:r|u|(?:user))/[0-9a-zA-Z_]+/comments/[0-9a-zA-Z]+/.+/?(?:\?.*)?\Z' 

    MAP_URL_ADDITION = 's/' 
    MAPMAKER_URL_TEMPLATE = 'https://mapmaker.deeeep.io/map/{}' 
    MAP_REGEX = '\A(?:(?:https?://)?(?:www\.)?mapmaker\.deeeep\.io/map/)?(?P<map_string_id>[0-9_A-Za-z]+)\Z' 

    PENDING_SKINS_LIST_URL = 'https://api.deeeep.io/skins/pending' 
    PENDING_MOTIONS_URL = 'https://api.deeeep.io/motions/pending?targetType=skin' 
    RECENT_MOTIONS_URL = 'https://api.deeeep.io/motions/recent?targetType=skin' 

    CHARACTER_TEMPLATE = 'https://deeeep.io/assets/characters/{}.png' 

    PENDING_FILTERS = {
        'reskin': lambda self, skin: skin['parent'], 
        'halloween': lambda self, skin: skin['season'] == 'hallooween', 
        'christmas': lambda self, skin: skin['season'] == 'christmas', 
        'valentines': lambda self, skin: skin['season'] == 'valentines', 
        'easter': lambda self, skin: skin['season'] == 'easter', 
        'acceptable': lambda self, skin: not self.reject_reasons(skin, check_reddit=False), 
        'unacceptable': lambda self, skin: self.reject_reasons(skin, check_reddit=False), 
        'realistic': lambda self, skin: skin['category'] == 'real', 
        'unrealistic': lambda self, skin: skin['category'] == 'unrealistic', 
        'stat-changing': lambda self, skin: skin['attributes'], 
        'non-stat-changing': lambda self, skin: not skin['attributes'], 
    } 

    FILTERS_STR = tools.format_iterable(PENDING_FILTERS.keys(), formatter='`{}`') 