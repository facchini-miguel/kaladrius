# Chilean Spanish (decision 120): 1.234,56 and dates as 31-10-2026. Django has no es_CL; what
# is not here comes from its es (Spain).
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
NUMBER_GROUPING = 3
SHORT_DATE_FORMAT = "d-m-Y"
SHORT_DATETIME_FORMAT = "d-m-Y H:i"
DATE_INPUT_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]
