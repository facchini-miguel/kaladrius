"""Django's own texts whose Brazilian Portuguese translation the project changes
(locale/pt_BR, decision 200): month names are lowercase in Portuguese ("30 de outubro de 2026"),
and Django 6.1 capitalizes them. Listed here only so makemessages keeps them in the catalog;
never read."""

from django.utils.translation import gettext_noop, pgettext_lazy

MONTHS = [
    gettext_noop("January"),
    gettext_noop("February"),
    gettext_noop("March"),
    gettext_noop("April"),
    gettext_noop("May"),
    gettext_noop("June"),
    gettext_noop("July"),
    gettext_noop("August"),
    gettext_noop("September"),
    gettext_noop("October"),
    gettext_noop("November"),
    gettext_noop("December"),
]
MONTHS_ALONE = [
    pgettext_lazy("alt. month", "January"),
    pgettext_lazy("alt. month", "February"),
    pgettext_lazy("alt. month", "March"),
    pgettext_lazy("alt. month", "April"),
    pgettext_lazy("alt. month", "May"),
    pgettext_lazy("alt. month", "June"),
    pgettext_lazy("alt. month", "July"),
    pgettext_lazy("alt. month", "August"),
    pgettext_lazy("alt. month", "September"),
    pgettext_lazy("alt. month", "October"),
    pgettext_lazy("alt. month", "November"),
    pgettext_lazy("alt. month", "December"),
]
