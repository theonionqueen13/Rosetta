import swisseph as swe

jd = swe.julday(1990, 7, 29, 7 + 39/60.0, swe.GREG_CAL)
lat = 38.046
lon = -97.345   # west negative!

cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
print("Ascendant =", ascmc[0])  # should be ~57.5° = Taurus 27°30′
