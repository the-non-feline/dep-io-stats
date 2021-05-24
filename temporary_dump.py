STAT_FORMATS = {
    'boosts': ('boosts', '{}'), 
    'tier': ('tier', '{}', lambda num: num + 1), 
    'oxygenTime': ('oxygen time', '{}s'), 
    'temperatureTime': ('temperature time', '{}s'),
    'pressureTime': ('pressure time', '{}s'),
    'salinityTime': ('salinity time', '{}s'),
    'speedMultiplier': ('base speed', '{:%}'),
    'walkSpeedMultiplier': ('walk speed', '{:%}'),
    'sizeMultiplier': ('size scale', '{}x', lambda num: float(num)), 
    'sizeScale': ('dimensions', "{0['x']} x {0['y']}"),
    'damageMultiplier': ('damage', '{}', lambda num: tools.trunc_float(num * 20)), 
    'healthMultiplier': ('health', '{} HP', lambda num: tools.trunc_float(num * 100)),
    'damageBlock': ('armor', '{}%', 100),
    'damageReflection': ('damage reflection', '{}%', 100), 
    'bleedReduction': ('bleed reduction', '{}%', 100), 
    'armorPenetration': ('armor penetration', '{}%', 100), 
    'habitat': ('habitat', '{}', habitat.Habitat(num)), 
    'secondaryAbilityLoadTime': ('charged boost load time', '{} ms'), 
}

BOOLEANS = 'canFly', 'canSwim', 'canStand', 'needsAir', 'canClimb', 'poisonResistant', 'ungrabbable', 'canDig', 'canWalkUnderwater' 

hasSecondaryAbility: !1,
hasWalkingAbility: !1,
jumpForceMultiplier: 1,