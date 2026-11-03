# Canadian English (decision 117): the government's year-month-day dates and the 12-hour clock.
# Django has no en_CA, so every date format is here.
DATE_FORMAT = "F j, Y"
TIME_FORMAT = "g:i A"
DATETIME_FORMAT = "F j, Y, g:i A"
YEAR_MONTH_FORMAT = "F Y"
MONTH_DAY_FORMAT = "F j"
SHORT_DATE_FORMAT = "Y-m-d"
SHORT_DATETIME_FORMAT = "Y-m-d g:i A"
FIRST_DAY_OF_WEEK = 0
DATE_INPUT_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
DATETIME_INPUT_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M"]
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3
