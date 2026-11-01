# South African English (decision 117): day/month and the 24-hour clock. Django has no en_ZA,
# so every date format is here (otherwise the American ones of config/formatos/en would win).
DATE_FORMAT = "j F Y"
TIME_FORMAT = "H:i"
DATETIME_FORMAT = "j F Y, H:i"
YEAR_MONTH_FORMAT = "F Y"
MONTH_DAY_FORMAT = "j F"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
FIRST_DAY_OF_WEEK = 1
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]
DATETIME_INPUT_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3
