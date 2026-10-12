"""Static lookup tables: API templates, property mapping tables, WMO and fanart code maps.

Pure data, no imports. config.py re-exports every name, so other modules keep using config.map_weather etc.
"""

# API
map_api = {
	'search': 'https://geocoding-api.open-meteo.com/v1/search?name={}&count=10&language=en&format=json&countrycode=US',
	'geoip': 'http://ip-api.com/json/?fields=status,city,regionName,countryCode',
	'weather': 'https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,dew_point_2m,precipitation_probability,visibility,uv_index,direct_radiation&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,pressure_msl,surface_pressure,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,is_day,direct_radiation&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,daylight_duration,sunshine_duration,uv_index_max,precipitation_hours,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant&timeformat=unixtime&forecast_days={}&past_days=1',
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
	[ "current",     [ 'current', "weather_code" ],               [ 'current', "fanartcode" ],                           "code" ],
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
	[ "hourly",      [ 'hourly', "temperature_2m" ],              [ 'hourly', "temperaturegraph" ],                      "temperaturekodi" ],
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
	[ "hourly",      [ 'hourly', "weather_code" ],                [ 'hourly', "fanartcode" ],                            "code" ],
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
	[ "daily",       [ 'daily', "weather_code" ],                 [ 'day', "fanartcode" ],                               "code" ],
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
	[ "daily",       [ 'daily', "precipitation_probability_max" ], [ 'day', "precipitation" ],                           "roundpercent" ],
	[ "daily",       [ 'daily', "wind_speed_10m_max" ],          [ 'day', "windspeed" ],                               "speedunit" ],
	[ "daily",       [ 'daily', "wind_direction_10m_dominant" ], [ 'day', "winddirection" ],                           "direction" ],

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
	'55d': 12,
	'55n': 12,
	'56d': 8,
	'56n': 8,
	'57d': 8,
	'57n': 8,
	'61d': 9,
	'61n': 9,
	'63d': 12,
	'63n': 12,
	'65d': 12,
	'65n': 12,
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
	'82d': 12,
	'82n': 12,
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

