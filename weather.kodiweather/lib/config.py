import os
import random
import xbmc
import xbmcvfs
import xbmcaddon

from . import utils

# API
map_api = {
	'search': 'https://geocoding-api.open-meteo.com/v1/search?name={}&count=10&language=en&format=json&countrycode=US',
	'geoip': 'http://ip-api.com/json/?fields=status,city,regionName,countryCode',
	'weather': 'https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,dew_point_2m,precipitation_probability,visibility,uv_index,direct_radiation&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,pressure_msl,surface_pressure,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,is_day,direct_radiation&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,daylight_duration,sunshine_duration,uv_index_max,precipitation_hours,precipitation_probability_max&timeformat=unixtime&forecast_days={}&past_days=1',
	'airquality': 'https://air-quality-api.open-meteo.com/v1/air-quality?latitude={}&longitude={}&current=us_aqi,pm10,pm2_5,carbon_monoxide,ozone,dust,nitrogen_dioxide,sulphur_dioxide&hourly=pm10,pm2_5,carbon_monoxide,ozone,dust,us_aqi,nitrogen_dioxide,sulphur_dioxide&timeformat=unixtime&forecast_days=4&past_days=1',
	'sun': 'https://api.met.no/weatherapi/sunrise/3.0/sun?lat={}&lon={}&date={}',
	'moon': 'https://api.met.no/weatherapi/sunrise/3.0/moon?lat={}&lon={}&date={}',
	'noaalerts': 'https://api.weather.gov/alerts/active?point={},{}',
	'iemradar': 'https://mesonet{}.agron.iastate.edu/cache/tile.py/1.0.0/{}/{}/{}/{}.png',
}

# Map Providers (base layer tiles)
map_providers = {
	'osm':            'https://tile.openstreetmap.org/{}/{}/{}.png',
	'carto_dark':     'https://a.basemaps.cartocdn.com/dark_all/{}/{}/{}.png',
	'carto_dark_nl':  'https://a.basemaps.cartocdn.com/dark_nolabels/{}/{}/{}.png',
	'carto_light':    'https://a.basemaps.cartocdn.com/light_all/{}/{}/{}.png',
	'carto_light_nl': 'https://a.basemaps.cartocdn.com/light_nolabels/{}/{}/{}.png',
	'carto_voyager':  'https://a.basemaps.cartocdn.com/rastertiles/voyager/{}/{}/{}.png',
	'opentopomap':    'https://a.tile.opentopomap.org/{}/{}/{}.png',
}

# IEM NEXRAD frame offsets (minutes ago)
# Layer names: nexrad-n0q (current), nexrad-n0q-m05m, nexrad-n0q-m10m, etc.
iem_frame_offsets = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

# Limits
try:
	maxdays = utils.setting('fcdays', 'int')
	if maxdays < 3:
		maxdays = 8  # Fallback if setting is missing, zero, or corrupt
except (ValueError, TypeError):
	maxdays = 8  # Fallback default if setting not available at import
mindays  = 1
maxhours = 72
minhours = 24
mindata  = 0
maxdata  = 300

# ADDON
addon_ua    = {'user-agent': f'{xbmc.getUserAgent()} (weather.kodiweather v{utils.xbmcaddon.Addon().getAddonInfo("version")})'}
addon_info  = f'{xbmc.getUserAgent()} (weather.kodiweather v{utils.xbmcaddon.Addon().getAddonInfo("version")})'
addon_data  = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
addon_cache = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile')) + "cache"
addon_icons = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path')) + "resources/icons"
addon_path  = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path'))
neterr      = 0

# Cache
dnscache = {}
mapcache = {}

# Modules (disabled)
# sys.path.append(f'{addon_path}/lib/modules')

# Mapping (Weather)
map_weather = [

	# Location
	[ "current",     [ 'latitude' ],                              [ 'current', 'latitude' ],                             'round2' ],
	[ "current",     [ 'latitude' ],                              [ 'current', 'season' ],                               'season' ],
	[ "current",     [ 'longitude' ],                             [ 'current', 'longitude' ],                            'round2' ],
	[ "current",     [ 'elevation' ],                             [ 'current', 'elevation' ],                            'round' ],

	# Units
	[ "current",     [ 'current_units', 'wind_speed_10m' ],       [ 'unit', 'speed' ],                                   'unitspeed' ],
	[ "current",     [ 'current_units', 'temperature_2m' ],       [ 'unit', 'temperature' ],                             'unittemperature' ],
	[ "current",     [ 'current_units', 'precipitation' ],        [ 'unit', 'precipitation' ],                           'unitprecipitation' ],
	[ "current",     [ 'current_units', 'snowfall' ],             [ 'unit', 'snow' ],                                    'unitsnow' ],
	[ "current",     [ 'current_units', 'pressure_msl' ],         [ 'unit', 'pressure' ],                                'unitpressure' ],
	[ "current",     [ 'current_units', 'relative_humidity_2m' ], [ 'unit', 'percent' ],                                 'unitpercent' ],
	[ "current",     [ 'hourly_units', 'visibility' ],            [ 'unit', 'distance' ],                                'unitdistance' ],
	[ "current",     [ 'hourly_units', 'direct_radiation' ],      [ 'unit', 'radiation' ],                               'unitradiation' ],
	[ "current",     [ 'hourly_units', 'direct_radiation' ],      [ 'unit', 'solarradiation' ],                          'unitradiation' ],

	# Current
	[ "current",     [ 'current', "time" ],                       [ 'current', "date" ],                                 "date" ],
	[ "current",     [ 'current', "time" ],                       [ 'current', "time" ],                                 "time" ],
	[ "current",     [ 'current', "time" ],                       [ 'current', "hour" ],                                 "hour" ],
	[ "current",     [ 'current', "temperature_2m" ],             [ 'current', "temperature" ],                          "temperaturekodi" ],
	[ "current",     [ 'current', "temperature_2m" ],             [ 'current', "temperatureaddon" ],                     "temperature" ],
	[ "currentkodi", [ 'current', "temperature_2m" ],             [ 'current', "temperature" ],                          "round" ],

	[ "current",     [ 'current', "apparent_temperature" ],       [ 'current', "feelslike" ],                            "temperaturekodi" ],
	[ "current",     [ 'current', "apparent_temperature" ],       [ 'current', "feelslikeaddon" ],                       "temperature" ],
	[ "currentkodi", [ 'current', "apparent_temperature" ],       [ 'current', "feelslike" ],                            "round" ],

	[ "current",     [ 'current', "dew_point_2m" ],               [ 'current', "dewpoint" ],                             "temperaturekodi" ],
	[ "current",     [ 'current', "dew_point_2m" ],               [ 'current', "dewpointaddon" ],                        "temperature" ],
	[ "currentkodi", [ 'current', "dew_point_2m" ],               [ 'current', "dewpoint" ],                             "round" ],

	[ "current",     [ 'current', "relative_humidity_2m" ],       [ 'current', "humidity" ],                             "%" ],
	[ "currentkodi", [ 'current', "relative_humidity_2m" ],       [ 'current', "humidity" ],                             "round" ],
	[ "current",     [ 'current', "relative_humidity_2m" ],       [ 'current', "humidityaddon" ],                        "round" ],

	[ "current",     [ 'current', "precipitation_probability" ],  [ 'current', "precipitation" ],                        "roundpercent" ],
	[ "current",     [ 'current', "precipitation" ],              [ 'current', "precipitationaddon" ],                   "precipitation" ],
	[ "current",     [ 'current', "precipitation_probability" ],  [ 'current', "precipitationprobability" ],             "round" ],
	[ "current",     [ 'current', "snowfall" ],                   [ 'current', "snow" ],                                 "snow" ],
	[ "current",     [ 'current', "pressure_msl" ],               [ 'current', "pressure" ],                             "pressure" ],
	[ "current",     [ 'current', "surface_pressure" ],           [ 'current', "pressuresurface" ],                      "pressure" ],
	[ "current",     [ 'current', "wind_speed_10m" ],             [ 'current', "wind" ],                                 "windkodi" ],
	[ "currentkodi", [ 'current', "wind_speed_10m" ],             [ 'current', "wind" ],                                 "round" ],

	[ "current",     [ 'current', "wind_speed_10m" ],             [ 'current', "windspeed" ],                            "speed" ],
	[ "current",     [ 'current', "wind_direction_10m" ],         [ 'current', "winddirection" ],                        "direction" ],
	[ "current",     [ 'current', "wind_direction_10m" ],         [ 'current', "winddirectiondegree" ],                  "round" ],
	[ "current",     [ 'current', "wind_gusts_10m" ],             [ 'current', "windgust" ],                             "speed" ],
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "condition" ],                            "wmocond" ],
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "outlookicon" ],                          "image" ],
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "outlookiconwmo" ],                       "wmoimage" ],
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "fanartcode" ],                           "code" ],
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "fanartcodewmo" ],                        "wmocode" ],
	[ "current",     [ 'current', "cloud_cover" ],                [ 'current', "cloudiness" ],                           "roundpercent" ],
	[ "current",     [ 'current', "cloud_cover" ],                [ 'current', "cloudinessaddon" ],                      "round" ],
	[ "current",     [ 'current', "is_day" ],                     [ 'current', "isday" ],                                "bool" ],
	[ "current",     [ 'current', "visibility" ],                 [ 'current', "visibility" ],                           "distance" ],
	[ "current",     [ 'current', "uv_index" ],                   [ 'current', "uvindex" ],                              "uvindex" ],
	[ "current",     [ 'current', "direct_radiation" ],           [ 'current', "solarradiation" ],                       "radiation" ],

	# Hourly
	[ "hourly",      [ 'hourly', "time" ],                        [ 'hourly', "date" ],                                  "date" ],
	[ "hourly",      [ 'hourly', "time" ],                        [ 'hourly', "shortdate" ],                             "date" ],
	[ "hourly",      [ 'hourly', "time" ],                        [ 'hourly', "time" ],                                  "time" ],
	[ "hourly",      [ 'hourly', "time" ],                        [ 'hourly', "hour" ],                                  "hour" ],
	[ "hourly",      [ 'hourly', "time" ],                        [ 'hourly', "longday" ],                               "weekday" ],
	[ "hourly",      [ 'hourly', "temperature_2m" ],              [ 'hourly', "temperature" ],                           "temperatureunit" ],
	[ "hourly",      [ 'hourly', "apparent_temperature" ],        [ 'hourly', "feelslike" ],                             "temperatureunit" ],
	[ "hourly",      [ 'hourly', "dew_point_2m" ],                [ 'hourly', "dewpoint" ],                              "temperatureunit" ],
	[ "hourly",      [ 'hourly', "relative_humidity_2m" ],        [ 'hourly', "humidity" ],                              "roundpercent" ],
	[ "hourly",      [ 'hourly', "precipitation_probability" ],   [ 'hourly', "precipitation" ],                         "roundpercent" ],
	[ "hourly",      [ 'hourly', "precipitation" ],               [ 'hourly', "precipitationaddon" ],                    "precipitation" ],
	[ "hourly",      [ 'hourly', "precipitation_probability" ],   [ 'hourly', "precipitationprobability" ],              "round" ],
	[ "hourly",      [ 'hourly', "precipitation_probability" ],   [ 'hourly', "chanceprecipitation" ],                   "roundpercent" ],
	[ "hourly",      [ 'hourly', "snowfall" ],                    [ 'hourly', "snow" ],                                  "snow" ],
	[ "hourly",      [ 'hourly', "pressure_msl" ],                [ 'hourly', "pressure" ],                              "pressure" ],
	[ "hourly",      [ 'hourly', "surface_pressure" ],            [ 'hourly', "pressuresurface" ],                       "pressure" ],
	[ "hourly",      [ 'hourly', "wind_speed_10m" ],              [ 'hourly', "windspeed" ],                             "speed" ],
	[ "hourly",      [ 'hourly', "wind_direction_10m" ],          [ 'hourly', "winddirection" ],                         "direction" ],
	[ "hourly",      [ 'hourly', "wind_direction_10m" ],          [ 'hourly', "winddirectiondegree" ],                   "round" ],
	[ "hourly",      [ 'hourly', "wind_gusts_10m" ],              [ 'hourly', "windgust" ],                              "speed" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "outlook" ],                               "wmocond" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "outlookicon" ],                           "image" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "outlookiconwmo" ],                        "wmoimage" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "fanartcode" ],                            "code" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "fanartcodewmo" ],                         "wmocode" ],
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "condition" ],                             "wmocond" ],
	[ "hourly",      [ 'hourly', "cloud_cover" ],                 [ 'hourly', "cloudiness" ],                            "roundpercent" ],
	[ "hourly",      [ 'hourly', "is_day" ],                      [ 'hourly', "isday" ],                                 "bool" ],
	[ "hourly",      [ 'hourly', "visibility" ],                  [ 'hourly', "visibility" ],                            "distance" ],
	[ "hourly",      [ 'hourly', "uv_index" ],                    [ 'hourly', "uvindex" ],                               "uvindex" ],
	[ "hourly",      [ 'hourly', "direct_radiation" ],            [ 'hourly', "solarradiation" ],                        "radiation" ],

	# Graphs
	[ "graph",      [ 'hourly', "temperature_2m" ],              [ 'hourly', "temperature.graph" ],                     "graph", "temperature" ],
	[ "graph",      [ 'hourly', "apparent_temperature" ],        [ 'hourly', "feelslike.graph" ],                       "graph", "temperature" ],
	[ "graph",      [ 'hourly', "dew_point_2m" ],                [ 'hourly', "dewpoint.graph" ],                        "graph", "temperature" ],
	[ "graph",      [ 'hourly', "relative_humidity_2m" ],        [ 'hourly', "humidity.graph" ],                        "graph", "round" ],
	[ "graph",      [ 'hourly', "precipitation" ],               [ 'hourly', "precipitation.graph" ],                   "graph", "precipitation" ],
	[ "graph",      [ 'hourly', "precipitation_probability" ],   [ 'hourly', "precipitationprobability.graph" ],        "graph", "round" ],
	[ "graph",      [ 'hourly', "snowfall" ],                    [ 'hourly', "snow.graph" ],                            "graph", "snow" ],
	[ "graph",      [ 'hourly', "pressure_msl" ],                [ 'hourly', "pressure.graph" ],                        "graph", "pressure" ],
	[ "graph",      [ 'hourly', "surface_pressure" ],            [ 'hourly', "pressuresurface.graph" ],                 "graph", "pressure" ],
	[ "graph",      [ 'hourly', "wind_speed_10m" ],              [ 'hourly', "windspeed.graph" ],                       "graph", "speed" ],
	[ "graph",      [ 'hourly', "wind_gusts_10m" ],              [ 'hourly', "windgust.graph" ],                        "graph", "speed" ],
	[ "graph",      [ 'hourly', "weather_code" ],                [ 'hourly', "condition.graph" ],                       "graph", "round" ],
	[ "graph",      [ 'hourly', "cloud_cover" ],                 [ 'hourly', "cloudiness.graph" ],                      "graph", "round" ],
	[ "graph",      [ 'hourly', "visibility" ],                  [ 'hourly', "visibility.graph" ],                      "graph", "distance" ],
	[ "graph",      [ 'hourly', "uv_index" ],                    [ 'hourly', "uvindex.graph" ],                         "graph", "uvindex" ],
	[ "graph",      [ 'hourly', "direct_radiation" ],            [ 'hourly', "solarradiation.graph" ],                  "graph", "radiation" ],

	# Daily
	[ "daily",       [ 'daily', "time" ],                         [ 'day', "title" ],                                    "weekday" ],
	[ "daily",       [ 'daily', "time" ],                         [ 'day', "date" ],                                     "date" ],
	[ "daily",       [ 'daily', "time" ],                         [ 'day', "shortdate" ],                                "date" ],
	[ "daily",       [ 'daily', "time" ],                         [ 'day', "shortday" ],                                 "weekdayshort" ],
	[ "daily",       [ 'daily', "time" ],                         [ 'day', "longday" ],                                  "weekday" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "condition" ],                                "wmocond" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "outlook" ],                                  "wmocond" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "outlookicon" ],                              "image" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "outlookiconwmo" ],                           "wmoimage" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "fanartcode" ],                               "code" ],
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "fanartcodewmo" ],                            "wmocode" ],
	[ "daily",       [ 'daily', "temperature_2m_max" ],           [ 'day', "hightemp" ],                                 "temperaturekodi" ],
	[ "dailykodi",   [ 'daily', "temperature_2m_max" ],           [ 'day', "hightemp" ],                                 "round" ],

	[ "daily",       [ 'daily', "temperature_2m_min" ],           [ 'day', "lowtemp" ],                                  "temperaturekodi" ],
	[ "dailykodi",   [ 'daily', "temperature_2m_min" ],           [ 'day', "lowtemp" ],                                  "round" ],

	[ "daily",       [ 'daily', "temperature_2m_max" ],           [ 'day', "hightemperature" ],                          "temperatureunit" ],
	[ "daily",       [ 'daily', "temperature_2m_min" ],           [ 'day', "lowtemperature" ],                           "temperatureunit" ],
	[ "daily",       [ 'daily', "sunrise" ],                      [ 'day', "sunrise" ],                                  "time" ],
	[ "daily",       [ 'daily', "sunset" ],                       [ 'day', "sunset" ],                                   "time" ],
	[ "daily",       [ 'daily', "daylight_duration" ],            [ 'day', "daylight" ],                                 "seconds" ],
	[ "daily",       [ 'daily', "sunshine_duration" ],            [ 'day', "sunshine" ],                                 "seconds" ],
	[ "daily",       [ 'daily', "precipitation_hours" ],          [ 'day', "precipitationhours" ],                       "round" ],
	[ "daily",       [ 'daily', "uv_index_max" ],                 [ 'day', "uvindex" ],                                  "uvindex" ],
	[ "daily",       [ 'daily', "precipitation_probability_max" ], [ 'day', "chanceprecipitation" ],                     "roundpercent" ],

	# Today
	[ "current",     [ 'daily', "sunrise", 3 ],                   [ 'today', "sunrise" ],                                "time" ],
	[ "current",     [ 'daily', "sunset", 3 ],                    [ 'today', "sunset" ],                                 "time" ],
	[ "current",     [ 'daily', "daylight_duration", 3 ],         [ 'today', "daylight" ],                               "seconds" ],
	[ "current",     [ 'daily', "sunshine_duration", 3 ],         [ 'today', "sunshine" ],                               "seconds" ],

	# TimeOfDay
	[ "timeofday",   [ 'hourly', "weather_code" ],                [ 'timeofday', "isfetched" ],                          "timeofday" ],
]

map_airquality = [

	# Units
	[ "current",    [ 'current_units', "pm10" ],          [ 'unit', "particles" ],                 "unitparticles" ],

	# Current
	[ "current",    [ 'current', "time" ],                [ 'current', "aqdate" ],                 "date" ],
	[ "current",    [ 'current', "time" ],                [ 'current', "aqtime" ],                 "time" ],
	[ "current",    [ 'current', "time" ],                [ 'current', "aqhour" ],                 "hour" ],
	[ "current",    [ 'current', "pm2_5" ],               [ 'current', "pm25" ],                   "particles" ],
	[ "current",    [ 'current', "pm10" ],                [ 'current', "pm10" ],                   "particles" ],
	[ "current",    [ 'current', "carbon_monoxide" ],     [ 'current', "co" ],                     "particles" ],
	[ "current",    [ 'current', "ozone" ],               [ 'current', "ozone" ],                  "particles" ],
	[ "current",    [ 'current', "dust" ],                [ 'current', "dust" ],                   "particles" ],
	[ "current",    [ 'current', "nitrogen_dioxide" ],    [ 'current', "no2" ],                    "particles" ],
	[ "current",    [ 'current', "sulphur_dioxide" ],     [ 'current', "so2" ],                    "particles" ],
	[ "current",    [ 'current', "us_aqi" ],              [ 'current', "aqius" ],                  "round" ],

	# Hourly
	[ "hourly",     [ 'hourly', "pm2_5" ],                [ 'hourly', "pm25" ],                    "particles" ],
	[ "hourly",     [ 'hourly', "pm10" ],                 [ 'hourly', "pm10" ],                    "particles" ],
	[ "hourly",     [ 'hourly', "carbon_monoxide" ],      [ 'hourly', "co" ],                      "particles" ],
	[ "hourly",     [ 'hourly', "ozone" ],                [ 'hourly', "ozone" ],                   "particles" ],
	[ "hourly",     [ 'hourly', "dust" ],                 [ 'hourly', "dust" ],                    "particles" ],
	[ "hourly",     [ 'hourly', "nitrogen_dioxide" ],     [ 'hourly', "no2" ],                     "particles" ],
	[ "hourly",     [ 'hourly', "sulphur_dioxide" ],      [ 'hourly', "so2" ],                     "particles" ],
	[ "hourly",     [ 'hourly', "us_aqi" ],               [ 'hourly', "aqius" ],                   "round" ],

	# Graphs
	[ "graph",     [ 'hourly', "pm2_5" ],                [ 'hourly', "pm25.graph" ],              "graph", "particles" ],
	[ "graph",     [ 'hourly', "pm10" ],                 [ 'hourly', "pm10.graph" ],              "graph", "particles" ],
	[ "graph",     [ 'hourly', "carbon_monoxide" ],      [ 'hourly', "co.graph" ],                "graph", "particles" ],
	[ "graph",     [ 'hourly', "ozone" ],                [ 'hourly', "ozone.graph" ],             "graph", "particles" ],
	[ "graph",     [ 'hourly', "dust" ],                 [ 'hourly', "dust.graph" ],              "graph", "particles" ],
	[ "graph",     [ 'hourly', "nitrogen_dioxide" ],     [ 'hourly', "no2.graph" ],               "graph", "particles" ],
	[ "graph",     [ 'hourly', "sulphur_dioxide" ],      [ 'hourly', "so2.graph" ],               "graph", "round" ],
	[ "graph",     [ 'hourly', "us_aqi" ],               [ 'hourly', "aqius.graph" ],             "graph", "round" ],
]

map_moon = [
	[ "current",    [ 'properties', 'moonrise', 'time' ],        [ 'today', "moonrise" ],              "timeiso" ],
	[ "current",    [ 'properties', 'moonrise', 'azimuth' ],     [ 'today', "moonriseazimuth" ],       "round" ],
	[ "current",    [ 'properties', 'moonset', 'time' ],         [ 'today', "moonset" ],               "timeiso" ],
	[ "current",    [ 'properties', 'moonset', 'azimuth' ],      [ 'today', "moonsetazimuth" ],        "round" ],
	[ "current",    [ 'properties', 'moonphase' ],               [ 'today', "moonphase" ],             "moonphase" ],
	[ "current",    [ 'properties', 'moonphase' ],               [ 'today', "moonphaseimage" ],        "moonphaseimage" ],
	[ "current",    [ 'properties', 'moonphase' ],               [ 'today', "moonphasedegree" ],       "round" ],
]

map = {
	'weather': map_weather,
	'airquality': map_airquality,
	'moon': map_moon,
}

# Alert (Condition)
map_alert_condition = {
		45: 'fog',
		48: 'fog',

		51: 'rain',
		53: 'rain',
		55: 'rain',
		61: 'rain',
		63: 'rain',
		65: 'rain',
		80: 'rain',
		81: 'rain',
		82: 'rain',
		56: 'rain',
		57: 'rain',
		66: 'rain',
		67: 'rain',

		71: 'snow',
		73: 'snow',
		75: 'snow',
		77: 'snow',
		85: 'snow',
		86: 'snow',

		95: 'storm',
		96: 'storm',
		99: 'storm',
}

# Mapping (IEM NEXRAD)
map_iemradar    = 'iemradar'  # Identifier for radar type
map_layers      = { 'iemradar': map_iemradar }

# Mapping WMO to KODI
map_wmo = {
	'0d': 32,
	'0n': 31,
	'1d': 34,
	'1n': 33,
	'2d': 30,
	'2n': 29,
	'3d': 26,
	'3n': 26,
	'45d': 20,
	'45n': 20,
	'48d': 20,
	'48n': 20,
	'51d': 9,
	'51n': 9,
	'53d': 12,
	'53n': 12,
	'55d': 18,
	'55n': 18,
	'56d': 8,
	'56n': 8,
	'57d': 8,
	'57n': 8,
	'61d': 9,
	'61n': 9,
	'63d': 12,
	'63n': 12,
	'65d': 18,
	'65n': 18,
	'66d': 8,
	'66n': 8,
	'67d': 8,
	'67n': 8,
	'71d': 14,
	'71n': 14,
	'73d': 16,
	'73n': 16,
	'75d': 16,
	'75n': 16,
	'77d': 13,
	'77n': 13,
	'80d': 9,
	'80n': 9,
	'81d': 12,
	'81n': 12,
	'82d': 18,
	'82n': 18,
	'85d': 5,
	'85n': 5,
	'86d': 5,
	'86n': 5,
	'95d': 4,
	'95n': 4,
	'96d': 3,
	'96n': 3,
	'99d': 3,
	'99n': 3,
}

# Fanart folder mapping - redirects clone codes to master folders
# This reduces resource.images.weatherfanart.echo size by ~1.2GB
# by eliminating duplicate image folders
map_fanart = {
	# Standalone (no redirect)
	0: 0,    # Tornado
	1: 1,    # Tropical Storm
	2: 2,    # Hurricane
	9: 9,    # Drizzle
	11: 11,  # Light Showers (Night)
	19: 19,  # Dust
	22: 22,  # Smoky
	25: 25,  # Cold
	# Masters + clones
	3: 3,    # Severe Thunderstorms (master)
	4: 3,    # Thunderstorms -> 3
	37: 3,   # Isolated Thunderstorms -> 3
	38: 3,   # Scattered Thunderstorms (Night) -> 3
	39: 3,   # Scattered Thunderstorms (Day) -> 3
	45: 3,   # Thundershowers -> 3
	47: 3,   # Isolated Thundershowers -> 3
	5: 5,    # Mixed Rain and Snow (master)
	6: 5,    # Mixed Rain and Sleet -> 5
	7: 5,    # Mixed Snow and Sleet -> 5
	8: 5,    # Freezing Drizzle -> 5
	10: 5,   # Freezing Rain -> 5
	18: 5,   # Sleet -> 5
	12: 12,  # Heavy Showers Day (master)
	40: 12,  # Scattered Showers -> 12
	13: 13,  # Snow Flurries (master)
	14: 13,  # Light Snow Showers -> 13
	15: 13,  # Blowing Snow -> 13
	16: 13,  # Snow -> 13
	41: 13,  # Heavy Snow (Night) -> 13
	42: 13,  # Scattered Snow Showers -> 13
	43: 13,  # Heavy Snow (Day) -> 13
	46: 13,  # Snow Showers -> 13
	17: 17,  # Hail (master)
	35: 17,  # Mixed Rain and Hail -> 17
	20: 20,  # Foggy (master)
	21: 20,  # Haze -> 20
	23: 23,  # Blustery (master)
	24: 23,  # Windy -> 23
	26: 26,  # Cloudy (master)
	28: 26,  # Mostly Cloudy (Day) -> 26
	30: 26,  # Partly Cloudy (Day) -> 26
	44: 26,  # Partly Cloudy -> 26
	27: 27,  # Mostly Cloudy Night (master)
	29: 27,  # Partly Cloudy (Night) -> 27
	31: 31,  # Clear Night (master)
	33: 31,  # Fair (Night) -> 31
	32: 32,  # Sunny (master)
	34: 32,  # Fair (Day) -> 32
	36: 32,  # Hot -> 32
}

def get_fanart_folder(code):
	"""Return the fanart folder for a given Yahoo weather code.
	   Redirects clone codes to their master folder."""
	return map_fanart.get(code, code)

# Fanart background - stable image selection
# Keyed by str(locid). Holds {'code': str, 'path': str} per location.
# Persists for the lifetime of the Kodi session so the same image is shown
# until the weather code or day/night state actually changes.
_fanartbg_state = {}

def get_fanartbg(code, locid):
	"""Return a stable full image path for the given fanart code and location.

	A new image is picked at random only when the code changes (i.e. when the
	weather condition or day/night state changes).  Between those events the
	same image is returned every time, so the home-screen background does not
	cycle or flicker.

	Returns a special:// path to a specific file, or '' if none can be found.
	"""
	key      = str(locid)
	code_str = str(code)
	entry    = _fanartbg_state.get(key, {})

	# Code unchanged and we already have a valid path — keep it.
	if entry.get('code') == code_str and entry.get('path'):
		return entry['path']

	# Code changed (or first run) — pick one image and lock it in.
	# Use special:// throughout — avoids os.path mixed separators on Windows.
	try:
		folder_uri = f'special://home/addons/resource.images.weatherfanart.echo/{code_str}/'
		_, files   = xbmcvfs.listdir(folder_uri)
		imgs       = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]

		if imgs:
			chosen = random.choice(imgs)
			path   = f'{folder_uri}{chosen}'
			_fanartbg_state[key] = {'code': code_str, 'path': path}
			return path
	except Exception:
		pass

	return ''

# Graph (Resolution)
map_height = {
	720: 720,
	1080: 1080,
	1440: 1440,
	2160: 2160,
	800: 720,
	1200: 1080,
	1600: 1440,
	2400: 2160
}

# Personalized forecast
map_fcstart = {
	0: None,
	1: 1,
	2: 2,
	3: 3,
	4: 4,
	5: 5,
	6: 6,
	7: 7,
	8: 8,
	9: 9,
	10: 10,
	11: 11,
	12: 12,
}
map_fcend = {
	24: None,
	23: -1,
	22: -2,
	21: -3,
	20: -4,
	19: -5,
	18: -6,
	17: -7,
	16: -8,
	15: -9,
	14: -10,
	13: -11,
	12: -12,
}

# Dynamic localization mapping
def localization():

	localization.wmo = {
		'0d': utils.locaddon(32200),
		'0n': utils.locaddon(32250),
		'1d': utils.locaddon(32201),
		'1n': utils.locaddon(32251),
		'2d': utils.locaddon(32202),
		'2n': utils.locaddon(32202),
		'3d': utils.locaddon(32203),
		'3n': utils.locaddon(32203),
		'45d': utils.locaddon(32204),
		'45n': utils.locaddon(32204),
		'48d': utils.locaddon(32205),
		'48n': utils.locaddon(32205),
		'51d': utils.locaddon(32206),
		'51n': utils.locaddon(32206),
		'53d': utils.locaddon(32207),
		'53n': utils.locaddon(32207),
		'55d': utils.locaddon(32208),
		'55n': utils.locaddon(32208),
		'56d': utils.locaddon(32209),
		'56n': utils.locaddon(32209),
		'57d': utils.locaddon(32210),
		'57n': utils.locaddon(32210),
		'61d': utils.locaddon(32211),
		'61n': utils.locaddon(32211),
		'63d': utils.locaddon(32212),
		'63n': utils.locaddon(32212),
		'65d': utils.locaddon(32213),
		'65n': utils.locaddon(32213),
		'66d': utils.locaddon(32214),
		'66n': utils.locaddon(32214),
		'67d': utils.locaddon(32215),
		'67n': utils.locaddon(32215),
		'71d': utils.locaddon(32216),
		'71n': utils.locaddon(32216),
		'73d': utils.locaddon(32217),
		'73n': utils.locaddon(32217),
		'75d': utils.locaddon(32218),
		'75n': utils.locaddon(32218),
		'77d': utils.locaddon(32219),
		'77n': utils.locaddon(32219),
		'80d': utils.locaddon(32220),
		'80n': utils.locaddon(32220),
		'81d': utils.locaddon(32221),
		'81n': utils.locaddon(32221),
		'82d': utils.locaddon(32222),
		'82n': utils.locaddon(32222),
		'85d': utils.locaddon(32223),
		'85n': utils.locaddon(32223),
		'86d': utils.locaddon(32224),
		'86n': utils.locaddon(32224),
		'95d': utils.locaddon(32225),
		'95n': utils.locaddon(32225),
		'96d': utils.locaddon(32226),
		'96n': utils.locaddon(32226),
		'99d': utils.locaddon(32227),
		'99n': utils.locaddon(32227)
	}

	localization.weekday = {
		'1': utils.loc(11),
		'2': utils.loc(12),
		'3': utils.loc(13),
		'4': utils.loc(14),
		'5': utils.loc(15),
		'6': utils.loc(16),
		'7': utils.loc(17)
	}

	localization.weekdayshort = {
		'1': utils.loc(41),
		'2': utils.loc(42),
		'3': utils.loc(43),
		'4': utils.loc(44),
		'5': utils.loc(45),
		'6': utils.loc(46),
		'7': utils.loc(47)
	}

	localization.timeofday = {
		0: utils.locaddon(32480),
		1: utils.locaddon(32481),
		2: utils.locaddon(32482),
		3: utils.locaddon(32483),
	}

	localization.layers = {
		'iemradar': utils.locaddon(32400),
	}

# Dynamic settings
def alert(cache=False):

	alert.map = {
	        'temperature.graph': {
			'type': 'temperature',
			'unit': 'temperature',
			'icon': 'temperature',
			'loc': 32320,
			'alert_temperature_high_1': utils.setting('alert_temperature_high_1', 'str', cache),
			'alert_temperature_high_2': utils.setting('alert_temperature_high_2', 'str', cache),
			'alert_temperature_high_3': utils.setting('alert_temperature_high_3', 'str', cache),
			'alert_temperature_low_1': utils.setting('alert_temperature_low_1', 'str', cache),
			'alert_temperature_low_2': utils.setting('alert_temperature_low_2', 'str', cache),
			'alert_temperature_low_3': utils.setting('alert_temperature_low_3', 'str', cache),
		},
	        'precipitation.graph': {
			'type': 'precipitation',
			'unit': 'precipitation',
			'icon': 'precipitation',
			'loc': 32321,
			'alert_precipitation_high_1': utils.setting('alert_precipitation_high_1', 'str', cache),
			'alert_precipitation_high_2': utils.setting('alert_precipitation_high_2', 'str', cache),
			'alert_precipitation_high_3': utils.setting('alert_precipitation_high_3', 'str', cache),
		},
	        'snow.graph': {
			'type': 'snow',
			'unit': 'snow',
			'icon': 'snow',
			'loc': 32217,
			'alert_snow_high_1': utils.setting('alert_snow_high_1', 'str', cache),
			'alert_snow_high_2': utils.setting('alert_snow_high_2', 'str', cache),
			'alert_snow_high_3': utils.setting('alert_snow_high_3', 'str', cache),
		},
	        'condition.graph': {
			'type': 'condition',
			'unit': '',
			'icon': 'condition',
			'loc': 32322,
			'alert_condition_wmo_1': utils.setting('alert_condition_wmo_1', 'str', cache),
			'alert_condition_wmo_2': utils.setting('alert_condition_wmo_2', 'str', cache),
			'alert_condition_wmo_3': utils.setting('alert_condition_wmo_3', 'str', cache),
		},
	        'windspeed.graph': {
			'type': 'windspeed',
			'unit': 'speed',
			'icon': 'wind',
			'loc': 32323,
			'alert_windspeed_high_1': utils.setting('alert_windspeed_high_1', 'str', cache),
			'alert_windspeed_high_2': utils.setting('alert_windspeed_high_2', 'str', cache),
			'alert_windspeed_high_3': utils.setting('alert_windspeed_high_3', 'str', cache),
		},
	        'windgust.graph': {
			'type': 'windgust',
			'unit': 'speed',
			'icon': 'wind',
			'loc': 32324,
			'alert_windgust_high_1': utils.setting('alert_windgust_high_1', 'str', cache),
			'alert_windgust_high_2': utils.setting('alert_windgust_high_2', 'str', cache),
			'alert_windgust_high_3': utils.setting('alert_windgust_high_3', 'str', cache),
		},
	        'feelslike.graph': {
			'type': 'feelslike',
			'unit': 'temperature',
			'icon': 'temperature',
			'loc': 32332,
			'alert_feelslike_high_1': utils.setting('alert_feelslike_high_1', 'str', cache),
			'alert_feelslike_high_2': utils.setting('alert_feelslike_high_2', 'str', cache),
			'alert_feelslike_high_3': utils.setting('alert_feelslike_high_3', 'str', cache),
			'alert_feelslike_low_1': utils.setting('alert_feelslike_low_1', 'str', cache),
			'alert_feelslike_low_2': utils.setting('alert_feelslike_low_2', 'str', cache),
			'alert_feelslike_low_3': utils.setting('alert_feelslike_low_3', 'str', cache),
		},
	        'dewpoint.graph': {
			'type': 'dewpoint',
			'unit': 'temperature',
			'icon': 'temperature',
			'loc': 32333,
			'alert_dewpoint_high_1': utils.setting('alert_dewpoint_high_1', 'str', cache),
			'alert_dewpoint_high_2': utils.setting('alert_dewpoint_high_2', 'str', cache),
			'alert_dewpoint_high_3': utils.setting('alert_dewpoint_high_3', 'str', cache),
			'alert_dewpoint_low_1': utils.setting('alert_dewpoint_low_1', 'str', cache),
			'alert_dewpoint_low_2': utils.setting('alert_dewpoint_low_2', 'str', cache),
			'alert_dewpoint_low_3': utils.setting('alert_dewpoint_low_3', 'str', cache),
		},
	        'cloudiness.graph': {
			'type': 'cloudiness',
			'unit': '%',
			'icon': 'cloud',
			'loc': 32334,
			'alert_cloudiness_high_1': utils.setting('alert_cloudiness_high_1', 'str', cache),
			'alert_cloudiness_high_2': utils.setting('alert_cloudiness_high_2', 'str', cache),
			'alert_cloudiness_high_3': utils.setting('alert_cloudiness_high_3', 'str', cache),
		},
	        'humidity.graph': {
			'type': 'humidity',
			'unit': '%',
			'icon': 'humidity',
			'loc': 32346,
			'alert_humidity_high_1': utils.setting('alert_humidity_high_1', 'str', cache),
			'alert_humidity_high_2': utils.setting('alert_humidity_high_2', 'str', cache),
			'alert_humidity_high_3': utils.setting('alert_humidity_high_3', 'str', cache),
		},
	        'precipitationprobability.graph': {
			'type': 'precipitationprobability',
			'unit': '%',
			'icon': 'precipitation',
			'loc': 32321,
			'alert_precipitationprobability_high_1': utils.setting('alert_precipitationprobability_high_1', 'str', cache),
			'alert_precipitationprobability_high_2': utils.setting('alert_precipitationprobability_high_2', 'str', cache),
			'alert_precipitationprobability_high_3': utils.setting('alert_precipitationprobability_high_3', 'str', cache),
		},
	        'pressure.graph': {
			'type': 'pressure',
			'unit': 'pressure',
			'icon': 'pressure',
			'loc': 32347,
			'alert_pressure_high_1': utils.setting('alert_pressure_high_1', 'str', cache),
			'alert_pressure_high_2': utils.setting('alert_pressure_high_2', 'str', cache),
			'alert_pressure_high_3': utils.setting('alert_pressure_high_3', 'str', cache),
			'alert_pressure_low_1': utils.setting('alert_pressure_low_1', 'str', cache),
			'alert_pressure_low_2': utils.setting('alert_pressure_low_2', 'str', cache),
			'alert_pressure_low_3': utils.setting('alert_pressure_low_3', 'str', cache),
		},
	        'pressuresurface.graph': {
			'type': 'pressuresurface',
			'unit': 'pressure',
			'icon': 'pressure',
			'loc': 32347,
			'alert_pressuresurface_high_1': utils.setting('alert_pressuresurface_high_1', 'str', cache),
			'alert_pressuresurface_high_2': utils.setting('alert_pressuresurface_high_2', 'str', cache),
			'alert_pressuresurface_high_3': utils.setting('alert_pressuresurface_high_3', 'str', cache),
			'alert_pressuresurface_low_1': utils.setting('alert_pressuresurface_low_1', 'str', cache),
			'alert_pressuresurface_low_2': utils.setting('alert_pressuresurface_low_2', 'str', cache),
			'alert_pressuresurface_low_3': utils.setting('alert_pressuresurface_low_3', 'str', cache),
		},
	        'solarradiation.graph': {
			'type': 'solarradiation',
			'unit': 'solarradiation',
			'icon': 'solarradiation',
			'loc': 32348,
			'alert_solarradiation_high_1': utils.setting('alert_solarradiation_high_1', 'str', cache),
			'alert_solarradiation_high_2': utils.setting('alert_solarradiation_high_2', 'str', cache),
			'alert_solarradiation_high_3': utils.setting('alert_solarradiation_high_3', 'str', cache),
		},
	        'visibility.graph': {
			'type': 'visibility',
			'unit': 'distance',
			'icon': 'visibility',
			'loc': 32349,
			'alert_visibility_low_1': utils.setting('alert_visibility_low_1', 'str', cache),
			'alert_visibility_low_2': utils.setting('alert_visibility_low_2', 'str', cache),
			'alert_visibility_low_3': utils.setting('alert_visibility_low_3', 'str', cache),
		},
	        'uvindex.graph': {
			'type': 'uvindex',
			'unit': 'uvindex',
			'icon': 'uvindex',
			'loc': 32329,
			'alert_uvindex_high_1': utils.setting('alert_uvindex_high_1', 'str', cache),
			'alert_uvindex_high_2': utils.setting('alert_uvindex_high_2', 'str', cache),
			'alert_uvindex_high_3': utils.setting('alert_uvindex_high_3', 'str', cache),
		},
	        'aqius.graph': {
			'type': 'aqius',
			'unit': 'index',
			'icon': 'health',
			'loc': 32326,
			'alert_aqius_high_1': utils.setting('alert_aqius_high_1', 'str', cache),
			'alert_aqius_high_2': utils.setting('alert_aqius_high_2', 'str', cache),
			'alert_aqius_high_3': utils.setting('alert_aqius_high_3', 'str', cache),
		},
	        'pm25.graph': {
			'type': 'pm25',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32327,
			'alert_pm25_high_1': utils.setting('alert_pm25_high_1', 'str', cache),
			'alert_pm25_high_2': utils.setting('alert_pm25_high_2', 'str', cache),
			'alert_pm25_high_3': utils.setting('alert_pm25_high_3', 'str', cache),
		},
	        'pm10.graph': {
			'type': 'pm10',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32328,
			'alert_pm10_high_1': utils.setting('alert_pm10_high_1', 'str', cache),
			'alert_pm10_high_2': utils.setting('alert_pm10_high_2', 'str', cache),
			'alert_pm10_high_3': utils.setting('alert_pm10_high_3', 'str', cache),
		},
	        'co.graph': {
			'type': 'co',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32337,
			'alert_co_high_1': utils.setting('alert_co_high_1', 'str', cache),
			'alert_co_high_2': utils.setting('alert_co_high_2', 'str', cache),
			'alert_co_high_3': utils.setting('alert_co_high_3', 'str', cache),
		},
		'ozone.graph': {
			'type': 'ozone',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32338,
			'alert_ozone_high_1': utils.setting('alert_ozone_high_1', 'str', cache),
			'alert_ozone_high_2': utils.setting('alert_ozone_high_2', 'str', cache),
			'alert_ozone_high_3': utils.setting('alert_ozone_high_3', 'str', cache),
		},
	        'dust.graph': {
			'type': 'dust',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32339,
			'alert_dust_high_1': utils.setting('alert_dust_high_1', 'str', cache),
			'alert_dust_high_2': utils.setting('alert_dust_high_2', 'str', cache),
			'alert_dust_high_3': utils.setting('alert_dust_high_3', 'str', cache),
		},
	        'no2.graph': {
			'type': 'no2',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32330,
			'alert_no2_high_1': utils.setting('alert_no2_high_1', 'str', cache),
			'alert_no2_high_2': utils.setting('alert_no2_high_2', 'str', cache),
			'alert_no2_high_3': utils.setting('alert_no2_high_3', 'str', cache),
		},
	        'so2.graph': {
			'type': 'so2',
			'unit': 'particles',
			'icon': 'particles',
			'loc': 32331,
			'alert_so2_high_1': utils.setting('alert_so2_high_1', 'str', cache),
			'alert_so2_high_2': utils.setting('alert_so2_high_2', 'str', cache),
			'alert_so2_high_3': utils.setting('alert_so2_high_3', 'str', cache),
		},
	}

def addon(cache=False):

	# Vars
	addon.settings   = utils.settings()
	addon.alerts     = 0
	addon.msgqueue   = []

	# Bool
	addon.debug       = utils.setting('debug', 'bool', cache)
	addon.verbose     = utils.setting('verbose', 'bool', cache)
	addon.enablehour  = utils.setting('enablehour', 'bool', cache)

	# Str
	addon.icons       = utils.setting('icons', 'str', cache)
	addon.unitsep     = utils.setting('unitsep', 'str', cache)
	addon.temp        = utils.setting('unittemp', 'str', cache)     or 'app'
	addon.tempdp      = utils.setting('unittempdp', 'str', cache)   or '1'
	addon.speed       = utils.setting('unitspeed', 'str', cache)    or 'mph'
	addon.speeddp     = utils.setting('unitspeeddp', 'str', cache)  or '1'
	addon.precip      = utils.setting('unitprecip', 'str', cache)   or 'in'
	addon.precipdp    = utils.setting('unitprecipdp', 'str', cache)  or '1'
	addon.snow        = utils.setting('unitsnow', 'str', cache)      or 'in'
	addon.snowdp      = utils.setting('unitsnowdp', 'str', cache)    or '1'
	addon.distance    = utils.setting('unitdistance', 'str', cache)  or 'mi'
	addon.distancedp  = utils.setting('unitdistancedp', 'str', cache) or '1'
	addon.particlesdp = utils.setting('unitparticlesdp', 'str', cache) or '1'
	addon.pollendp    = utils.setting('unitpollendp', 'str', cache)  or '1'
	addon.uvindexdp   = utils.setting('unituvindexdp', 'str', cache) or '1'
	addon.pressure    = utils.setting('unitpressure', 'str', cache)  or 'inHg'
	addon.pressuredp  = utils.setting('unitpressuredp', 'str', cache) or '0'
	addon.radiationdp = utils.setting('unitradiationdp', 'str', cache) or '1'
	addon.cdefault    = utils.setting('colordefault', 'str', cache)
	addon.cnegative   = utils.setting('colornegative', 'str', cache)
	addon.cnormal     = utils.setting('colornormal', 'str', cache)
	addon.cnotice     = utils.setting('colornotice', 'str', cache)
	addon.ccaution    = utils.setting('colorcaution', 'str', cache)
	addon.cdanger     = utils.setting('colordanger', 'str', cache)

	# Int
	addon.mapzoom     = utils.setting('mapzoom', 'int', cache)
	addon.maphistory  = utils.setting('maphistory', 'int', cache)
	addon.alerthours  = max(1, utils.setting('alert_hours', 'int', cache))
	addon.fcstart     = utils.setting('fcstart', 'int', cache)
	addon.fcend       = utils.setting('fcend', 'int', cache)

	# Map settings
	addon.mapprovider = utils.setting('mapprovider', 'str', cache) or 'osm'

	# Maxlocs
	if utils.setting('explocations', 'bool', cache):
		addon.maxlocs = 6
	else:
		addon.maxlocs = 4

def kodi():
	kodi.long     = utils.region('datelong')
	kodi.date     = utils.region('dateshort')
	kodi.time     = utils.region('time')
	kodi.meri     = utils.region('meridiem')
	kodi.speed    = utils.region('speedunit')
	kodi.temp     = utils.region('tempunit')
	kodi.height   = 1080

def loc(locid, cache=False):
	loc.prop = {}
	loc.id   = locid
	loc.cid  = str(utils.settingrpc("weather.currentlocation") or 1)
	loc.lat  = utils.setting(f'loc{locid}lat', 'float')
	loc.lon  = utils.setting(f'loc{locid}lon', 'float')
	loc.utz  = utils.setting(f'loc{locid}utz', 'bool')

	# Name
	name = utils.setting(f'loc{locid}', 'str')
	user = utils.setting(f'loc{locid}user', 'str')

	if user:
		loc.name  = user
		loc.short = user
	else:
		loc.name  = name
		loc.short = name.split(',')[0]

	# Timezone
	try:
		loc.tz = utils.timezone(utils.setting(f'loc{locid}tz'))
	except:
		loc.tz = utils.timezone('UTC')

def init(cache=False):
	kodi()
	localization()
	addon(cache)
	alert(cache)

	# Directory
	utils.createdir()

