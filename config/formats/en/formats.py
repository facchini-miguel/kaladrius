# English date formats with "AM"/"PM" instead of Django's "a.m."/"p.m." (decision 116):
# a sentence ending in a time got two periods ("Last sample: 10/31/2026 11:15 p.m..").
# Everything not listed here comes from Django's own English formats.
TIME_FORMAT = "g:i A"
DATETIME_FORMAT = "N j, Y, g:i A"
SHORT_DATETIME_FORMAT = "m/d/Y g:i A"
